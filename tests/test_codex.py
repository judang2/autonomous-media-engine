import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from igagent.core import ConfigurationError, Config, decide
from igagent.providers import Mock
from igagent.codex_planner import child_environment, check_login, parse_events, generate


class CodexTests(unittest.TestCase):
    def test_credentials_not_inherited(self):
        with patch.dict(os.environ, {'IG_PASSWORD':'secret', 'IG_GRAPH_TOKEN':'secret',
                        'OPENAI_API_KEY':'secret', 'CODEX_API_KEY':'secret', 'PATH':'path'}, clear=True):
            self.assertEqual(child_environment(), {'PATH':'path'})

    def test_api_login_rejected(self):
        result = subprocess.CompletedProcess([], 0, 'Logged in using an API key', '')
        with patch('igagent.codex_planner.subprocess.run', return_value=result):
            with self.assertRaises(ConfigurationError):
                check_login('codex', {})

    def test_tool_activity_rejected(self):
        event = {'type':'item.completed', 'item':{'type':'command_execution'}}
        with self.assertRaises(ConfigurationError):
            parse_events(json.dumps(event))

    def test_missing_completion_rejected(self):
        with self.assertRaises(ConfigurationError):
            parse_events('{}')

    def test_codex_dispatch_without_api_key(self):
        s = Mock().observe()
        action = {'kind':'noop', 'event_id':'', 'text':'', 'reason':'nothing'}
        with patch.dict(os.environ, {}, clear=True), patch('igagent.codex_planner.generate', return_value=action):
            self.assertEqual(decide(Config(planner='codex'), s, s['events']).kind, 'noop')

    def test_process_contract_and_usage_log(self):
        answer = {'kind':'noop', 'event_id':'', 'text':'', 'reason':'nothing'}
        events = [{'type':'item.completed', 'item':{'type':'agent_message','text':json.dumps(answer)}},
                  {'type':'turn.completed', 'usage':{'input_tokens':200, 'cached_input_tokens':100, 'output_tokens':20}}]
        result = subprocess.CompletedProcess([], 0, '\n'.join(map(json.dumps, events)), '')
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            with patch('igagent.codex_planner.executable', return_value='codex'), patch('igagent.codex_planner.check_login'):
                with patch('igagent.codex_planner.subprocess.run', return_value=result) as run:
                    self.assertEqual(generate('instructions', {}, {}, Path(folder)), answer)
                    args = run.call_args.args[0]
                    self.assertIn('gpt-5.5', args)
                    self.assertIn('model_reasoning_effort="low"', args)
                    self.assertIn('forced_login_method="chatgpt"', args)
                    self.assertIn('features.shell_tool=false', args)
                    self.assertNotIn('shell', run.call_args.kwargs)
            log = json.loads((Path(folder)/'model-usage.jsonl').read_text())
            self.assertEqual(log['usage']['input_tokens'], 200)
            self.assertNotIn('instructions', str(log))
