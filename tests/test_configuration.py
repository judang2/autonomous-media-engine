import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from igagent.core import ConfigurationError, flag, load_env
from igagent.providers import private_login


class ConfigurationTests(unittest.TestCase):
    def test_bad_boolean_does_not_echo_value(self):
        with patch.dict(os.environ, {'ACK_PRIVATE_API_RISK': 'private-secret'}):
            with self.assertRaises(ConfigurationError) as error:
                flag('ACK_PRIVATE_API_RISK')
        self.assertNotIn('private-secret', str(error.exception))
        self.assertIn('true or false', str(error.exception))

    def test_disabled_login_explains_setting_without_network(self):
        with patch.dict(os.environ, {'ACK_PRIVATE_API_RISK': 'false'}):
            with self.assertRaises(ConfigurationError) as error:
                private_login()
        self.assertIn('ACK_PRIVATE_API_RISK=true', str(error.exception))

    def test_bad_line_reports_number_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('# heading\nprivate-secret', encoding='utf-8')
            with self.assertRaises(ConfigurationError) as error:
                load_env(path)
        self.assertIn('line 2', str(error.exception))
        self.assertNotIn('private-secret', str(error.exception))
