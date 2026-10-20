"""Run from repo root: python -m tools.autonomous_worker --help."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time

from .github import GitHub
from .runner import Uncertain, execute, preflight
from .state import Store


def worker(config, key, token):
    store = Store(config['database'], config.get('maximum_workers', 3))
    api = GitHub(os.environ.get('FFXI_GITHUB_TOKEN'))
    try:
        execute(config, store.get(key), store, token, api)
    except Uncertain:
        store.transition(key, token, 'uncertain', 'worker/publication outcome uncertain; inspect runner and branch')
    except Exception as e:
        # Known execution failure after the adapter has reaped the process group.
        # Do not echo exception content: commands/HTTP libraries can contain sensitive strings.
        row = store.get(key)
        if row['state'] in ('claimed', 'running'):
            store.transition(key, token, 'retry_wait', f'{type(e).__name__}: offline attempt failed; inspect isolated runner', retry=True)
    finally:
        store.db.close()


def tick(config, store, api, pool, futures):
    store.expire(config.get('heartbeat_timeout_seconds', 180))
    futures[:] = [f for f in futures if not f.done()]
    ready, blocked = api.discover()
    for repo, number, spec in ready:
        store.enqueue(repo, number, spec)
    # Discovery is read-only unless run mode is explicitly enabled.
    for row in store.jobs():
        if row['state'] not in ('queued', 'retry_wait'):
            continue
        approved = config.get('approved_issues', {}).get(row['id'])
        if not approved or approved != json.loads(row['spec'])['body_hash']:
            continue
        try:
            fresh, _ = api.fresh(row['repo'], row['issue'], self_claim=row['state'] == 'retry_wait')
        except ValueError as e:
            blocked.append({'repo': row['repo'], 'issue': row['issue'], 'reason': str(e)})
            continue
        token = store.claim(row['id'], fresh)
        if token:
            futures.append(pool.submit(worker, config, row['id'], token))
    api.notify(store)
    return blocked


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['discover', 'run', 'status', 'resolve'])
    p.add_argument('--config', required=True)
    p.add_argument('--job')
    p.add_argument('--expected-state')
    p.add_argument('--evidence')
    p.add_argument('--once', action='store_true')
    args = p.parse_args()
    config = json.loads(Path(args.config).read_text())
    store = Store(config['database'], config.get('maximum_workers', 3))
    if args.command == 'status':
        print(json.dumps([{k: v for k, v in r.items() if k != 'token'} for r in store.jobs()], indent=2))
        return
    if args.command == 'resolve':
        store.resolve(args.job, args.expected_state, args.evidence or '')
        return
    api = GitHub(os.environ.get('FFXI_GITHUB_TOKEN'))
    if args.command == 'discover':
        ready, blocked = api.discover()
        print(json.dumps({'eligible': ready, 'blocked': blocked}, indent=2))
        return
    preflight(config)  # missing execution backend must not claim jobs
    if config.get('heartbeat_timeout_seconds', 180) < 60:
        raise ValueError('heartbeat timeout must be at least 60 seconds')
    with ThreadPoolExecutor(max_workers=config.get('maximum_workers', 3)) as pool:
        futures = []
        while True:
            try:
                tick(config, store, api, pool, futures)
            except Exception as e:
                # API failures never become an empty queue; persisted claims remain conservative.
                print(json.dumps({'error': type(e).__name__, 'action': 'discovery/notification failed; retry next tick'}), flush=True)
                if args.once:
                    raise
            if args.once:
                for f in futures:
                    f.result()
                api.notify(store)
                return
            time.sleep(15)


if __name__ == '__main__':
    main()
