"""Fail-closed GitHub discovery; issue prose never supplies executable commands."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request
from .state import canonical, overlaps

REPOS = ('sarthax/darkstar-to-valhalla', 'sarthax/xiheadless-dsp', 'sarthax/FFXI-Mission-Toolkit')


def watcher():
    path = Path(__file__).resolve().parents[2] / '.github/scripts/ready_watch.py'
    spec = importlib.util.spec_from_file_location('worker_ready_watch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(issue):
    return hashlib.sha256((issue.get('body') or '').encode()).hexdigest()


class GitHub:
    def __init__(self, token):
        if not token:
            raise ValueError('controller GitHub token required')
        self.token = token

    def call(self, repo, method, path, body=None):
        if repo not in REPOS or not path.startswith('/') or '..' in path:
            raise ValueError('repository/path outside allowlist')
        req = urllib.request.Request('https://api.github.com/repos/' + repo + path,
                                     data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={'Authorization': 'Bearer ' + self.token,
                                              'Accept': 'application/vnd.github+json',
                                              'X-GitHub-Api-Version': '2022-11-28'})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            # Never log response bodies, tokens, or issue-provided content.
            raise RuntimeError(f'GitHub {method} {repo}{path}: HTTP {e.code}') from None

    def pages(self, repo, path):
        rows = []
        for page in range(1, 101):
            chunk = self.call(repo, 'GET', path + ('&' if '?' in path else '?') + f'per_page=100&page={page}')
            rows.extend(chunk)
            if len(chunk) < 100:
                return rows
        raise RuntimeError('pagination limit; cannot assert complete ownership')

    def snapshot(self, repo):
        issues = [i for i in self.pages(repo, '/issues?state=open') if 'pull_request' not in i]
        prs = []
        for pr in self.pages(repo, '/pulls?state=open'):
            files = self.pages(repo, f"/pulls/{pr['number']}/files")
            if len(files) >= 3000:
                raise RuntimeError('PR file API truncated; coordinator review required')
            pr['owned'] = [p for f in files for p in (f['filename'], f.get('previous_filename')) if p]
            prs.append(pr)
        return issues, prs

    def eligible(self, repo, issue, peers, prs, self_claim=False):
        rw = watcher()
        labels = {l['name'] for l in issue.get('labels', [])}
        if issue['state'] != 'open' or 'pull_request' in issue or 'ready' not in labels:
            raise ValueError('not an open ready issue')
        if issue.get('assignees') or ('in-progress' in labels and not self_claim):
            raise ValueError('already owned')
        if not labels.intersection({'agent:remote-safe', 'agent:hybrid'}):
            raise ValueError('remote eligibility requires coordinator label')
        if any(l in labels for l in ('blocked', 'agent:local-only', 'needs-local-test')):
            raise ValueError('blocked/local-only issue')
        spec = rw.spec_of(issue)
        if not spec['owned'] or not spec['accept'] or not spec['dont']:
            raise ValueError('incomplete issue specification')
        for p in spec['owned']:
            canonical(p)
        for peer in peers:
            pl = {l['name'] for l in peer.get('labels', [])}
            if peer['number'] != issue['number'] and pl.intersection({'ready', 'in-progress'}):
                theirs = rw.spec_of(peer)['owned']
                if 'in-progress' in pl and not theirs:
                    raise ValueError('active issue has unknown ownership')
                if any(overlaps(a, b) for a in spec['owned'] for b in theirs):
                    raise ValueError(f"ownership overlaps issue #{peer['number']}")
        for pr in prs:
            if any(overlaps(a, b) for a in spec['owned'] for b in pr['owned']):
                raise ValueError(f"ownership overlaps PR #{pr['number']}")
        sections = rw.sections(issue.get('body'))
        deps = rw.find(sections, 'depends on', 'dependencies')
        if deps is None:
            raise ValueError('dependencies must be explicit')
        if not spec['deps'] and re.sub(r'[-*`\s.]', '', deps).lower() not in ('none', 'nonelisted'):
            raise ValueError('unparsed dependencies need coordinator')
        for ref in spec['deps']:
            name, number = ref.rsplit('#', 1)
            target = name or repo
            dep = self.call(target, 'GET', f'/issues/{int(number)}')
            if dep['state'] != 'closed':
                raise ValueError(f'dependency {ref} is open')
            if 'pull_request' in dep and not self.call(target, 'GET', f'/pulls/{int(number)}').get('merged_at'):
                raise ValueError(f'dependency {ref} was not merged')
        base_text = rw.find(sections, 'base branch') or ''
        match = re.match(r'^`([^`]+)`|^([A-Za-z0-9_./-]+)', base_text)
        if not match:
            raise ValueError('explicit base branch required')
        base = match.group(1) or match.group(2)
        if base != 'main' and not base.startswith('feature/'):
            raise ValueError('unsupported base; coordinator required')
        return {'owned': spec['owned'], 'base': base, 'body_hash': digest(issue)}

    def discover(self, repos=REPOS):
        result, blocked = [], []
        for repo in repos:
            issues, prs = self.snapshot(repo)
            for issue in issues:
                if not any(l['name'] == 'ready' for l in issue.get('labels', [])):
                    continue
                try:
                    spec = self.eligible(repo, issue, issues, prs)
                    result.append((repo, issue['number'], spec))
                except ValueError as e:
                    blocked.append({'repo': repo, 'issue': issue['number'], 'reason': str(e)})
        return result, blocked

    def fresh(self, repo, number, self_claim=False):
        issues, prs = self.snapshot(repo)
        issue = self.call(repo, 'GET', f'/issues/{number}')
        return self.eligible(repo, issue, issues, prs, self_claim), issue

    def notify(self, store):
        """Durable outbox, idempotent event marker; leave failures pending."""
        pending = store.db.execute('''SELECT e.*,j.repo,j.issue FROM outbox o JOIN events e ON e.id=o.event
             JOIN jobs j ON j.id=e.job WHERE o.sent=0 ORDER BY e.id''').fetchall()
        for event in pending:
            # Include job key as well as event ID so a different DB cannot collide silently.
            marker = '<!-- ffxi-worker:' + hashlib.sha256((event['job'] + ':' + str(event['id'])).encode()).hexdigest() + ' -->'
            comments = self.pages(event['repo'], f"/issues/{event['issue']}/comments")
            if not any(marker in (c.get('body') or '') for c in comments):
                self.call(event['repo'], 'POST', f"/issues/{event['issue']}/comments", {'body':
                    f"{marker}\nWorker job `{event['job']}`: **{event['state']}**.\n\n{event['detail']}\n\n"
                    'Claude Code/owner retains live testing, review and merge. No automatic merge.'})
            store.db.execute('UPDATE outbox SET sent=1 WHERE event=?', (event['id'],))
