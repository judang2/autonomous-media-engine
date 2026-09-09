import importlib.util
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec('instagrapi'), 'optional private dependency not installed')
class PrivateContractTests(unittest.TestCase):
    def test_timeout_and_challenge_never_retry(self):
        from igagent.private_client import make_client, enforce_no_retries
        from instagrapi.exceptions import ClientRequestTimeout, ChallengeRequired
        client = make_client()
        enforce_no_retries(client)
        self.assertEqual(client.request_timeout, 1)
        self.assertEqual(client.private.get_adapter('https://').max_retries.total, 0)
        for error in (ClientRequestTimeout, ChallengeRequired):
            with patch.object(client, '_send_private_request', side_effect=error) as send:
                with patch.object(client, 'challenge_resolve', side_effect=AssertionError) as challenge:
                    with self.assertRaises(error):
                        client.private_request('test/', data={'message': 'hello'})
                    self.assertEqual(send.call_count, 1)
                    challenge.assert_not_called()

    def test_session_and_real_model_contract(self):
        from igagent.private_client import make_client
        from instagrapi.types import Comment, DirectThread
        client = make_client()
        client.set_settings({'authorization_data': {'ds_user_id': '123', 'sessionid': 'fake-test'}})
        self.assertEqual(str(client.user_id), '123')
        self.assertIn('created_at_utc', Comment.model_fields)
        self.assertIn('messages', DirectThread.model_fields)
        with patch.object(client, '_send_private_request', return_value={'status': 'ok'}) as send:
            self.assertEqual(client.private_request('test/'), {'status': 'ok'})
            self.assertIn('Authorization', send.call_args.kwargs['headers'])

    def test_bounded_requests(self):
        from igagent.private_client import make_client
        client = make_client()
        client.request_budget = 0
        with patch.object(client, '_send_private_request') as send:
            with self.assertRaises(RuntimeError):
                client.private_request('test/')
            send.assert_not_called()
