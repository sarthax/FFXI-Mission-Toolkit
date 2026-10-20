"""Synthetic, offline simulations; no credentials, accounts or game services."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from tools.autonomous_worker.state import Store, overlaps, canonical
from tools.autonomous_worker.github import GitHub
from tools.autonomous_worker.runner import changes, preflight, git, run_process, execute, container_command, container_run, Uncertain

REPO = 'sarthax/xiheadless-dsp'


def spec(path='a.py'):
    return {'owned': [path], 'base': 'main', 'body_hash': 'synthetic'}


def issue(n=1, path='a.py', extra=''):
    return {'number': n, 'state': 'open', 'labels': [{'name': 'ready'}, {'name': 'agent:remote-safe'}],
            'assignees': [], 'body': f'## Files owned\n- {path}\n## Do not touch\n- other files\n'
            '## Acceptance criteria\n- synthetic test\n## Depends on\n- none\n## Base branch\nmain\n' + extra}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'jobs.db')
        self.now = [1000.0]
        self.s = Store(self.path, clock=lambda: self.now[0])

    def tearDown(self):
        self.s.db.close()
        self.tmp.cleanup()

    def add(self, n, path='a.py'):
        return self.s.enqueue(REPO, n, spec(path))

    def test_atomic_duplicate_claim(self):
        key = self.add(1)
        def claim(_):
            s = Store(self.path)
            try:
                return bool(s.claim(key, spec()))
            finally:
                s.db.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            self.assertEqual(sum(ex.map(claim, range(8))), 1)

    def test_global_three_worker_ceiling_under_contention(self):
        keys = [self.add(i, f'{i}.py') for i in range(12)]
        def claim(key):
            s = Store(self.path)
            try:
                return bool(s.claim(key, spec(key.split('#')[1] + '.py')))
            finally:
                s.db.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
            self.assertEqual(sum(ex.map(claim, keys)), 3)

    def test_directory_and_glob_conservative_overlap(self):
        self.assertTrue(overlaps('Mcp/', 'Mcp/a.cs'))
        self.assertTrue(overlaps('Mcp/*/a.cs', 'Mcp/b/b.cs'))
        self.assertTrue(overlaps('*.cs', 'docs/a.md'))
        a, b = self.add(1, 'Mcp/'), self.add(2, 'Mcp/a.cs')
        self.assertTrue(self.s.claim(a, spec('Mcp/')))
        self.assertIsNone(self.s.claim(b, spec('Mcp/a.cs')))

    def test_bad_paths(self):
        for path in ('../a', '/tmp/a', 'a/../b', 'a\\b', './a', 'a//b'):
            with self.assertRaises(ValueError):
                canonical(path)

    def test_heartbeat_expiry_quarantines_and_fences(self):
        key = self.add(1)
        token = self.s.claim(key, spec())
        self.s.transition(key, token, 'running')
        self.now[0] += 181
        self.s.expire()
        self.assertEqual(self.s.get(key)['state'], 'uncertain')
        with self.assertRaises(ValueError):
            self.s.heartbeat(key, token)
        self.assertIsNone(self.s.claim(self.add(2), spec()))
        self.s.resolve(key, 'uncertain', 'synthetic proof worker stopped')
        self.assertTrue(self.s.claim(f'{REPO}#2', spec()))

    def test_retry_backoff_and_limit(self):
        key = self.add(1)
        for attempt in range(3):
            token = self.s.claim(key, spec())
            self.assertTrue(token)
            self.s.transition(key, token, 'retry_wait', retry=True)
            self.assertIsNone(self.s.claim(key, spec()))
            self.now[0] += 1000
        self.assertEqual(self.s.get(key)['state'], 'failed')

    def test_review_retains_file_lock_releases_capacity(self):
        key = self.add(1)
        token = self.s.claim(key, spec())
        self.s.transition(key, token, 'running')
        self.s.transition(key, token, 'awaiting_review', 'synthetic PR')
        self.assertIsNone(self.s.claim(self.add(2), spec()))
        self.assertTrue(self.s.claim(self.add(3, 'b.py'), spec('b.py')))

    def test_restart_events_and_outbox_persist(self):
        self.add(1)
        other = Store(self.path)
        self.assertEqual(other.get(f'{REPO}#1')['state'], 'queued')
        self.assertEqual(other.db.execute('SELECT count(*) FROM outbox WHERE sent=0').fetchone()[0], 1)
        other.db.close()

    def test_spec_changed_cannot_claim(self):
        key = self.add(1)
        self.assertIsNone(self.s.claim(key, spec('b.py')))

    def test_persisted_capacity_policy(self):
        with self.assertRaises(ValueError):
            Store(self.path, maximum=1)

    def test_cross_repository_global_capacity(self):
        for n, repo in enumerate((REPO, 'sarthax/darkstar-to-valhalla', 'sarthax/FFXI-Mission-Toolkit')):
            key = self.s.enqueue(repo, n, spec())
            self.assertTrue(self.s.claim(key, spec()))
        self.assertIsNone(self.s.claim(self.add(99, 'unrelated.py'), spec('unrelated.py')))

    def test_stale_token_cannot_finish_new_attempt(self):
        key = self.add(1)
        old = self.s.claim(key, spec())
        self.s.transition(key, old, 'retry_wait', retry=True)
        self.now[0] += 1000
        token = self.s.claim(key, spec())
        self.assertNotEqual(old, token)
        with self.assertRaises(ValueError):
            self.s.transition(key, old, 'running')

    def test_bad_maximum(self):
        for n in (0, 4):
            with self.assertRaises(ValueError):
                Store(self.path, maximum=n)

    def test_no_retry_without_termination_proof(self):
        key = self.add(1)
        token = self.s.claim(key, spec())
        with self.assertRaises(ValueError):
            self.s.transition(key, token, 'retry_wait')


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.api = GitHub('synthetic-not-a-token')

    def test_ready_issue_and_child_base(self):
        i = issue()
        self.assertEqual(self.api.eligible(REPO, i, [i], [])['owned'], ['a.py'])
        i['body'] = i['body'].replace('\nmain\n', '\n`feature/parent` (PR head)\n')
        self.assertEqual(self.api.eligible(REPO, i, [i], [])['base'], 'feature/parent')

    def test_owner_label_and_pr_rename_conflicts(self):
        i = issue()
        for key, val in [('assignees', [{'login': 'synthetic'}]), ('state', 'closed')]:
            bad = dict(i, **{key: val})
            with self.assertRaises(ValueError):
                self.api.eligible(REPO, bad, [bad], [])
        with self.assertRaises(ValueError):
            self.api.eligible(REPO, i, [i], [{'number': 9, 'owned': ['a.py']}])
        with self.assertRaises(ValueError):
            self.api.eligible(REPO, i, [i, issue(2)], [])

    def test_dependencies_fail_closed(self):
        i = issue()
        i['body'] = i['body'].replace('- none', '- #99')
        with patch.object(self.api, 'call', return_value={'state': 'open'}):
            with self.assertRaises(ValueError):
                self.api.eligible(REPO, i, [i], [])
        with patch.object(self.api, 'call', side_effect=RuntimeError('synthetic API error')):
            with self.assertRaises(RuntimeError):
                self.api.eligible(REPO, i, [i], [])

    def test_unknown_dependencies_rejected(self):
        i = issue()
        i['body'] = i['body'].replace('- none', '- ask someone first')
        with self.assertRaises(ValueError):
            self.api.eligible(REPO, i, [i], [])

    def test_notification_recovers_lost_post_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Store(str(Path(tmp) / 'jobs.db'))
            s.enqueue(REPO, 1, spec())
            comments = []
            def post(*args):
                comments.append(args[-1])
                raise RuntimeError('synthetic response loss after write')
            with patch.object(self.api, 'pages', side_effect=lambda *a: comments), patch.object(self.api, 'call', side_effect=post):
                with self.assertRaises(RuntimeError):
                    self.api.notify(s)
                self.api.notify(s)
            self.assertEqual(len(comments), 1)
            self.assertEqual(s.db.execute('SELECT sent FROM outbox').fetchone()[0], 1)
            s.db.close()


class RunnerTests(unittest.TestCase):
    def test_unavailable_backend_claims_nothing(self):
        with self.assertRaises(RuntimeError):
            preflight({'isolated_host': False})
        with patch('shutil.which', return_value=None):
            with self.assertRaises(RuntimeError):
                preflight({'isolated_host': True})

    def test_scope_rejects_untracked_outside_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp)
            git(w, 'init', '-b', 'main')
            git(w, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '--allow-empty', '-m', 'base')
            (w / 'allowed.py').write_text('synthetic')
            self.assertEqual(changes(w, 'HEAD', ['allowed.py'])[0][0], 'allowed.py')
            (w / 'outside.py').write_text('synthetic')
            with self.assertRaises(ValueError):
                changes(w, 'HEAD', ['allowed.py'])


class ExecutionTests(unittest.TestCase):
    def test_container_boundary_for_tests(self):
        config = {'image': 'synthetic@sha256:123', 'model_network': 'model-only'}
        _, cmd = container_command(config, Path('/synthetic/repo'), ['python', '-m', 'unittest'])
        self.assertEqual(cmd[cmd.index('--network') + 1], 'none')
        self.assertNotIn('/auth/auth.json', ' '.join(cmd))
        self.assertIn('type=bind,src=/synthetic/repo/.git,dst=/workspace/.git,readonly', cmd)
        self.assertNotIn('FFXI_GITHUB_TOKEN', ' '.join(cmd))
        self.assertIn('--read-only', cmd)

    def test_daemon_outage_is_uncertain(self):
        config = {'image': 'synthetic@sha256:123', 'model_network': 'model-only'}
        with patch('tools.autonomous_worker.runner.run_process'), patch('subprocess.run', side_effect=OSError('synthetic')):
            with self.assertRaises(Uncertain):
                container_run(config, ['true'], Path('/synthetic'), None, 'job', 'token')

    def test_full_simulated_agent_to_draft_pr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mirror = root / 'mirror'
            mirror.mkdir()
            git(mirror, 'init', '-b', 'main')
            (mirror / 'AGENTS.md').write_text('Synthetic fixture: offline only')
            (mirror / 'CLAUDE.md').write_text('Synthetic fixture: reuse rules')
            (mirror / '.github').mkdir()
            (mirror / '.github/PULL_REQUEST_TEMPLATE.md').write_text('## Summary\n## Local test checklist\n')
            git(mirror, 'add', 'AGENTS.md', 'CLAUDE.md', '.github/PULL_REQUEST_TEMPLATE.md')
            git(mirror, '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', 'commit', '-m', 'synthetic base')
            base = git(mirror, 'rev-parse', 'HEAD').decode().strip()
            store = Store(str(root / 'state.db'))
            key = store.enqueue(REPO, 1, spec())
            token = store.claim(key, spec())
            api = GitHub('synthetic')
            calls = []
            def call(repo, method, path, body=None):
                calls.append((method, path, body))
                if path.startswith('/git/ref/'):
                    return {'object': {'sha': base}}
                if path.startswith('/git/commits/'):
                    return {'tree': {'sha': 'synthetic-tree'}}
                if path == '/pulls':
                    return {'number': 99, 'html_url': 'https://example.invalid/synthetic-pr'}
                return {'sha': 'synthetic-sha'}
            def agent(config, argv, work, *args, **kwargs):
                if kwargs.get('agent'):
                    (work / 'a.py').write_text('# clearly synthetic fixture\n')
            config = {'model_proxy_url': 'https://example.invalid/v1', 'repositories': {REPO: {'mirror': str(mirror), 'tests': [['python', '-m', 'unittest']]}}}
            with patch('tools.autonomous_worker.runner.preflight'), patch.object(api, 'fresh', return_value=(spec(), issue())), patch.object(api, 'call', side_effect=call), patch('tools.autonomous_worker.runner.container_run', side_effect=agent):
                execute(config, store.get(key), store, token, api)
            self.assertEqual(store.get(key)['state'], 'awaiting_review')
            pr = next(body for method, path, body in calls if path == '/pulls')
            self.assertEqual(pr['base'], 'main')
            self.assertTrue(pr['draft'])
            branch = next(body for method, path, body in calls if path == '/git/refs')
            self.assertTrue(branch['ref'].startswith('refs/heads/codex/1-'))
            self.assertFalse(any('merge' in path for _, path, _ in calls))
            store.db.close()


if __name__ == '__main__':
    unittest.main()
