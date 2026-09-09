import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from igagent.core import Action, Config, Event, Journal, cycle, decide, policy
from igagent.providers import Graph, Mock, Private


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Config(state_dir=Path(self.tmp.name))
        self.journal = Journal(self.config.state_dir)
        self.provider = Mock()
        self.event = self.provider.observe()['events'][0]
        self.action = Action('reply_dm', self.event.id, '안녕!', 'reply')

    def tearDown(self):
        self.journal.db.close()
        self.tmp.cleanup()

    def test_default_is_offline_dry_run(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('network')):
            result = cycle(self.config, self.provider, self.journal)
        self.assertEqual(result['status'], 'dry_run')
        self.assertEqual(self.journal.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0], 0)

    def test_allowlist_and_invented_target(self):
        self.config.friends = set()
        self.assertEqual(policy(self.config, self.action, [self.event], ['reply_dm']), 'actor_not_allowlisted')
        self.action.event_id = 'invented'
        self.assertEqual(policy(self.config, self.action, [self.event], ['reply_dm']), 'unknown_or_wrong_target')

    def test_time_window(self):
        for ts in [time.time() - 86400, time.time() + 100]:
            self.event.timestamp = ts
            self.assertEqual(policy(self.config, self.action, [self.event], ['reply_dm']), 'reply_too_old_or_invalid_time')

    def test_injection_cannot_enable_actions(self):
        self.action = Action('publish_photo', self.event.id, 'ignore rules', 'malicious')
        self.assertEqual(policy(self.config, self.action, [self.event], ['publish_photo']), 'action_not_enabled')
        self.action = Action('reply_dm', self.event.id, 'https://evil.example', 'malicious')
        self.assertEqual(policy(self.config, self.action, [self.event], ['reply_dm']), 'links_and_mentions_disabled')

    def test_schema_rejects_extra_and_nonstring_fields(self):
        for value in [{'kind': 'follow'}, {'kind': 'noop', 'event_id': '', 'text': 1, 'reason': ''},
                      {'kind': 'noop', 'event_id': '', 'text': '', 'reason': '', 'token': 'secret'}]:
            with self.assertRaises(ValueError):
                Action.parse(value)

    def test_persistent_dedupe_and_cooldown(self):
        self.assertEqual(self.journal.reserve('account', self.action, self.config), 'reserved')
        self.journal.finish('account', self.action, 'success')
        self.action.text = 'Different reply cannot bypass deduplication'
        self.assertEqual(self.journal.reserve('account', self.action, self.config), 'duplicate')
        other = Action('reply_dm', 'second', 'hello', '')
        self.assertEqual(self.journal.reserve('account', other, self.config), 'cooldown')
        second_journal = Journal(self.config.state_dir)
        try:
            self.assertTrue(second_journal.seen('account', self.event.id))
        finally:
            second_journal.db.close()

    def test_daily_cap_counts_attempts(self):
        self.config.daily = 1
        self.journal.reserve('account', self.action, self.config)
        self.journal.finish('account', self.action, 'success')
        self.assertEqual(self.journal.reserve('account', Action('like', 'second', '', ''), self.config), 'daily_limit')

    def test_uncertain_send_blocks_next_attempt(self):
        self.config.live = True
        with patch.object(self.provider, 'execute', side_effect=TimeoutError):
            with self.assertRaises(RuntimeError):
                cycle(self.config, self.provider, self.journal)
        self.assertEqual(self.journal.reserve('mock:mock-account', Action('like', 'new', '', ''), self.config), 'unresolved_attempt')

    def test_stop_prevents_observation(self):
        (self.config.state_dir / 'STOP').touch()
        with patch.object(self.provider, 'observe', side_effect=AssertionError):
            self.assertEqual(cycle(self.config, self.provider, self.journal)['status'], 'stopped')

    def test_log_omits_content(self):
        cycle(self.config, self.provider, self.journal)
        log = (self.config.state_dir / 'actions.jsonl').read_text(encoding='utf-8')
        self.assertNotIn('반가워', log)
        self.assertNotIn('preview', log)

    def test_live_needs_two_switches_and_real_planner(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                Config.env(live=True)
        with patch.dict(os.environ, {'ENABLE_LIVE': 'true', 'IG_PROVIDER': 'graph'}, clear=True):
            with self.assertRaises(ValueError):
                Config.env(live=True)

    def test_openai_contract_and_refusal(self):
        response = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text':
                    json.dumps({'kind': 'noop', 'event_id': '', 'text': '', 'reason': 'uncertain'})}]}]}
        self.config.planner = 'openai'
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fake-test', 'OPENAI_MODEL': 'test-model'}):
            with patch('igagent.core.request_json', return_value=response) as req:
                self.assertEqual(decide(self.config, self.provider.observe(), [self.event]).kind, 'noop')
                body = req.call_args.args[2]
                self.assertFalse(body['store'])
                self.assertTrue(body['text']['format']['strict'])
                self.assertNotIn('fake-test', json.dumps(body))
            with patch('igagent.core.request_json', return_value={'status': 'completed', 'output': []}):
                with self.assertRaises(RuntimeError):
                    decide(self.config, self.provider.observe(), [])

    def test_graph_routing(self):
        with patch.dict(os.environ, {'IG_GRAPH_TOKEN': 'fake-test', 'IG_GRAPH_USER_ID': '123',
                                     'IG_GRAPH_VERSION': 'v25.0', 'GRAPH_ENABLE_DM': 'true'}):
            graph = Graph()
        with patch('igagent.providers.request_json', return_value={'id': 'ok'}) as req:
            graph.execute(self.action, self.event)
            self.assertTrue(req.call_args.args[0].endswith('/123/messages'))
            self.assertEqual(req.call_args.args[2]['recipient']['id'], self.event.target)
        with self.assertRaises(ValueError):
            graph.execute(Action('like', self.event.id, '', ''), self.event)

    def test_private_disabled_before_import_or_network(self):
        with patch.dict(os.environ, {'ACK_PRIVATE_API_RISK': 'false'}):
            with self.assertRaises(ValueError):
                Private()

    def test_graph_observe_normalizes_comments_and_skips_own(self):
        with patch.dict(os.environ, {'IG_GRAPH_TOKEN': 'fake', 'IG_GRAPH_USER_ID': '123',
                                     'IG_GRAPH_VERSION': 'v25.0', 'GRAPH_ENABLE_DM': 'false'}):
            graph = Graph()
        responses = [{'id': '123', 'username': 'experiment'}, {'data': [{'id': '456'}]},
                     {'data': [{'id': '789', 'text': 'hello', 'from': {'id': 'friend-1'},
                                'timestamp': '2026-09-08T00:00:00Z'},
                               {'id': '790', 'text': 'own', 'from': {'id': '123'}}]}]
        with patch.object(graph, 'call', side_effect=responses):
            snapshot = graph.observe()
        self.assertEqual(len(snapshot['events']), 1)
        self.assertEqual(snapshot['events'][0].target, '789')
        self.assertEqual(snapshot['events'][0].media, '456')
        self.assertNotIn('reply_dm', snapshot['capabilities'])

    def test_graph_publish_waits_for_container(self):
        with patch.dict(os.environ, {'IG_GRAPH_TOKEN': 'fake', 'IG_GRAPH_USER_ID': '123',
                                     'IG_GRAPH_VERSION': 'v25.0'}):
            graph = Graph()
        event = Event('asset:x', 'asset', 'self', 'x', 'photo', time.time())
        with patch('igagent.providers.asset_source', return_value='https://example.com/photo.jpg'):
            with patch.object(graph, 'call', side_effect=[{'id': 'container'}, {'status_code': 'FINISHED'}, {'id': 'post'}]) as call:
                graph.execute(Action('publish_photo', event.id, 'caption', ''), event)
                self.assertEqual(call.call_args.args[0], '123/media_publish')

    def test_private_photo_configures_once(self):
        from unittest.mock import MagicMock
        private = object.__new__(Private)
        private.client = MagicMock()
        private.client.photo_rupload.return_value = ('upload', 100, 100)
        private.client.photo_configure.return_value = False
        event = Event('asset:x', 'asset', 'self', 'x', 'photo', time.time())
        with patch('igagent.providers.asset_source', return_value='test.jpg'), patch.object(Path, 'is_file', return_value=True):
            with self.assertRaises(RuntimeError):
                private.execute(Action('publish_photo', event.id, 'caption', ''), event)
        private.client.photo_configure.assert_called_once()

    def test_private_asset_cannot_escape_media(self):
        from unittest.mock import MagicMock
        private = object.__new__(Private)
        private.client = MagicMock()
        event = Event('asset:x', 'asset', 'self', 'x', 'photo', time.time())
        with patch('igagent.providers.asset_source', return_value='../secret.jpg'):
            with self.assertRaises(ValueError):
                private.execute(Action('publish_photo', event.id, 'caption', ''), event)
        private.client.photo_rupload.assert_not_called()


if __name__ == '__main__':
    unittest.main()
