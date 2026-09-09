"""Version-pinned, fail-closed boundary around instagrapi's request layer."""
import logging


def make_client(strict=True):
    from instagrapi import Client

    quiet = logging.Logger('instagram-experiment-private')
    quiet.addHandler(logging.NullHandler())
    quiet.propagate = False

    class SingleAttemptClient(Client):
        request_budget = 20

        def private_request(self, endpoint, data=None, params=None, **kwargs):
            if self.request_budget <= 0:
                raise RuntimeError('private_request_budget_exhausted')
            self.request_budget -= 1
            headers = dict(kwargs.pop('headers', None) or {})
            if self.authorization:
                headers['Authorization'] = self.authorization
            # Call the transport once. Do not enter upstream retry/challenge handling.
            self.private_requests_count += 1
            return self._send_private_request(endpoint, data=data, params=params, headers=headers, **kwargs)

    # instagrapi uses request_timeout as a PRE-REQUEST SLEEP, not a socket timeout.
    client = (SingleAttemptClient if strict else Client)(request_timeout=1, session_retry_total=0, logger=quiet)
    client.private_request_logger = quiet
    return client


def enforce_no_retries(client):
    # Imported session settings must not re-enable HTTP adapter retries.
    client.set_retry_config(request_timeout=1, session_retry_total=0, public_request_retries_count=0)
