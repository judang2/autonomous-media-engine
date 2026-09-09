import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from igagent.core import Config, ConfigurationError
from igagent.owner import bind_owner, load_owner


class OwnerTests(unittest.TestCase):
    def test_bound_identity_scoped_to_account_and_provider(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'OWNER_USERNAME':'example_owner'}):
            config = Config(provider='private', state_dir=Path(folder))
            provider = SimpleNamespace(client=MagicMock())
            provider.client.user_id = 123
            provider.client.user_info_by_username_v1.return_value = SimpleNamespace(username='example_owner', pk=456)
            bind_owner(config, provider)
            self.assertEqual(load_owner(config, 123)['user_id'], '456')
            self.assertIsNone(load_owner(config, 999))
            config.provider = 'graph'
            self.assertIsNone(load_owner(config, 123))

    def test_lookup_mismatch_not_saved(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'OWNER_USERNAME':'example_owner'}):
            config = Config(provider='private', state_dir=Path(folder))
            provider = SimpleNamespace(client=MagicMock())
            provider.client.user_info_by_username_v1.return_value = SimpleNamespace(username='someone_else', pk=456)
            with self.assertRaises(ConfigurationError):
                bind_owner(config, provider)
            self.assertFalse((Path(folder)/'owner.json').exists())
