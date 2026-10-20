"""Single durable SQLite authority; use local disk, never independent replica DBs."""
import contextlib
import json
import secrets
import sqlite3
import time

HOLD = ('claimed', 'running', 'retry_wait', 'uncertain', 'awaiting_review')
ACTIVE = ('claimed', 'running', 'uncertain')


def canonical(path):
    if not isinstance(path, str) or not path or path.startswith('/'):
        raise ValueError('ownership must be a relative path')
    # Globs are conservatively locked as their entire static parent directory.
    if '\\' in path or any(p in ('', '.', '..') for p in path.rstrip('/').split('/')):
        raise ValueError('non-canonical ownership')
    for index, char in enumerate(path):
        if char in '*?[':
            prefix = path[:index]
            return prefix.rsplit('/', 1)[0] + '/' if '/' in prefix else './'
    return path


def overlaps(a, b):
    a, b = canonical(a) if a != './' else a, canonical(b) if b != './' else b
    return a == './' or b == './' or a == b or a.startswith(b.rstrip('/') + '/') or b.startswith(a.rstrip('/') + '/')


class Store:
    def __init__(self, path, maximum=3, clock=time.time):
        if not 1 <= maximum <= 3:
            raise ValueError('maximum must be 1..3')
        self.maximum, self.clock = maximum, clock
        self.db = sqlite3.connect(path, timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, repo TEXT NOT NULL, issue INTEGER NOT NULL,
          spec TEXT NOT NULL, state TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0,
          token TEXT, heartbeat REAL, due REAL NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '',
          UNIQUE(repo,issue));
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY, job TEXT NOT NULL, at REAL NOT NULL, state TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outbox (
          event INTEGER PRIMARY KEY, sent INTEGER NOT NULL DEFAULT 0);
        ''')

        with self.tx():
            self.db.execute("INSERT OR IGNORE INTO settings VALUES('maximum', ?)", (str(maximum),))
            if self.db.execute("SELECT value FROM settings WHERE key='maximum'").fetchone()[0] != str(maximum):
                raise ValueError('all controllers must use the same persisted concurrency setting')

    @contextlib.contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def event(self, job, state, detail):
        cur = self.db.execute('INSERT INTO events(job,at,state,detail) VALUES(?,?,?,?)',
                              (job, self.clock(), state, detail))
        self.db.execute('INSERT INTO outbox(event) VALUES(?)', (cur.lastrowid,))

    def enqueue(self, repo, issue, spec):
        owned = spec.get('owned', [])
        if not owned:
            raise ValueError('empty ownership')
        for p in owned:
            canonical(p)
        key = f'{repo}#{issue}'
        with self.tx():
            old = self.get(key)
            if old and old['state'] != 'queued':
                return key
            if old:
                self.db.execute('UPDATE jobs SET spec=? WHERE id=?', (json.dumps(spec), key))
            else:
                self.db.execute('INSERT INTO jobs(id,repo,issue,spec,state) VALUES(?,?,?,?,?)',
                                (key, repo, issue, json.dumps(spec), 'queued'))
                self.event(key, 'queued', 'eligible discovery')
        return key

    def get(self, key):
        r = self.db.execute('SELECT * FROM jobs WHERE id=?', (key,)).fetchone()
        return dict(r) if r else None

    def jobs(self):
        return [dict(r) for r in self.db.execute('SELECT * FROM jobs ORDER BY id')]

    def claim(self, key, validated_spec):
        """Atomic capacity + ownership + token. Caller must freshly validate GitHub first."""
        with self.tx():
            row = self.get(key)
            if not row or row['state'] not in ('queued', 'retry_wait') or row['due'] > self.clock():
                return None
            if json.loads(row['spec']) != validated_spec:
                return None
            held = [r for r in self.jobs() if r['state'] in HOLD and r['id'] != key]
            if sum(r['state'] in ACTIVE for r in held) >= self.maximum:
                return None
            for r in held:
                if r['repo'] == row['repo'] and any(overlaps(a, b) for a in validated_spec['owned']
                                                   for b in json.loads(r['spec'])['owned']):
                    return None
            token = secrets.token_hex(24)
            self.db.execute("UPDATE jobs SET state='claimed', token=?, heartbeat=?, attempt=attempt+1 WHERE id=?",
                            (token, self.clock(), key))
            self.event(key, 'claimed', 'atomic ownership reserved')
            return token

    def transition(self, key, token, state, detail='', retry=False, max_attempts=3):
        allowed = {'claimed': {'running', 'failed', 'retry_wait', 'uncertain'},
                   'running': {'awaiting_review', 'failed', 'retry_wait', 'uncertain'}}
        with self.tx():
            row = self.get(key)
            if not row or row['token'] != token or state not in allowed.get(row['state'], set()):
                raise ValueError('stale token or invalid transition')
            if state == 'retry_wait':
                # Only call after proving no worker remains; stale heartbeats never retry automatically.
                if not retry:
                    raise ValueError('retry requires confirmed termination')
                if row['attempt'] >= max_attempts:
                    state = 'failed'
            due = self.clock() + min(3600, 30 * 2 ** row['attempt']) if state == 'retry_wait' else 0
            self.db.execute('UPDATE jobs SET state=?,detail=?,due=?,heartbeat=? WHERE id=?',
                            (state, detail, due, self.clock(), key))
            self.event(key, state, detail)

    def heartbeat(self, key, token):
        with self.tx():
            cur = self.db.execute("UPDATE jobs SET heartbeat=? WHERE id=? AND token=? AND state IN ('claimed','running')",
                                  (self.clock(), key, token))
            if not cur.rowcount:
                raise ValueError('fenced worker')

    def expire(self, seconds=180):
        with self.tx():
            for r in self.jobs():
                if r['state'] in ('claimed', 'running') and self.clock() - r['heartbeat'] > seconds:
                    self.db.execute("UPDATE jobs SET state='uncertain',detail='heartbeat expired' WHERE id=?", (r['id'],))
                    self.event(r['id'], 'uncertain', 'heartbeat expired; locks retained, coordinator must prove worker stopped')

    def resolve(self, key, expected_state, detail):
        """Explicit coordinator release after verifying termination or reviewed PR disposition."""
        if expected_state not in ('queued', 'retry_wait', 'uncertain', 'awaiting_review', 'failed') or not detail.strip():
            raise ValueError('coordinator evidence required')
        with self.tx():
            r = self.get(key)
            if not r or r['state'] != expected_state:
                raise ValueError('state changed')
            self.db.execute("UPDATE jobs SET state='resolved',token=NULL,detail=? WHERE id=?", (detail, key))
            self.event(key, 'resolved', detail)
