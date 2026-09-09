import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as Obj
from unittest.mock import Mock
from igagent.chat import Inbox, available
from igagent.core import Config, Journal, Action


class ChatTests(unittest.TestCase):
    def test_primary_groups_allowed_but_general_pending_self_missing_excluded(self):
        now = time.time()
        def thread(actor, folder=0, pending=False):
            return Obj(id=actor, users=[None, None], folder=folder, pending=pending,
                       messages=[Obj(id=actor, user_id=actor, text='hello',
                                     timestamp=datetime.fromtimestamp(now, timezone.utc))])
        provider = Mock()
        provider.client.user_id = 'self'
        unknown = thread('missing')
        del unknown.folder
        provider.client.direct_threads_chunk.return_value = ([thread('new-person'), thread('general', 1), thread('request', pending=True), thread('self'), unknown], None)
        inbox = Inbox(provider, set(), now-1, primary=True)
        self.assertEqual([e.actor for e in inbox.poll()], ['new-person'])
        provider.client.direct_threads_chunk.assert_called_once_with(box='primary', thread_message_limit=1)
        provider.client.direct_threads.assert_not_called()

    def test_inbox_only_new_allowed_individual_messages(self):
        now = time.time()
        def thread(actor, age=0, users=1):
            return Obj(id=actor, users=[None]*users, messages=[Obj(id=actor, user_id=actor, text='hello', timestamp=datetime.fromtimestamp(now-age, timezone.utc))])
        provider = Mock()
        provider.client.user_id = 'self'
        provider.client.direct_threads.return_value = [thread('owner'), thread('other'), thread('old', 100), thread('group', users=2)]
        inbox = Inbox(provider, {'owner','old','group'}, now-1)
        self.assertEqual([e.actor for e in inbox.poll()], ['owner'])
        inbox.considered.add('dm:owner')
        self.assertEqual(inbox.poll(), [])
        provider.client.user_medias_v1.assert_not_called()

    def test_preflight_stops_at_daily_limit(self):
        with tempfile.TemporaryDirectory() as d:
            journal = Journal(Path(d))
            config = Config(daily=100, cooldown=0)
            for i in range(100):
                action = Action('reply_dm', str(i), 'hi', '')
                self.assertEqual(journal.reserve('scope', action, config), 'reserved')
                journal.finish('scope', action, 'success')
            self.assertEqual(available(config, journal, 'scope'), 'daily_limit')
            journal.db.close()

    def test_pending_prevents_new_polling(self):
        with tempfile.TemporaryDirectory() as d:
            journal = Journal(Path(d))
            config = Config(cooldown=0)
            journal.reserve('scope', Action('reply_dm', 'one', 'hi', ''), config)
            self.assertEqual(available(config, journal, 'scope'), 'unresolved_attempt')
            journal.db.close()
