"""Explicit, bounded interactive DM experiment. No background service."""
import json
import time
from .core import ConfigurationError, Event, cycle
from .owner import load_owner
from .providers import timestamp


def available(config, journal, scope):
    if journal.db.execute("SELECT 1 FROM attempts WHERE scope=? AND status IN ('pending','unknown')", (scope,)).fetchone():
        return 'unresolved_attempt'
    rows = journal.db.execute('SELECT ts FROM attempts WHERE scope=? AND ts>?', (scope, time.time()-86400)).fetchall()
    if len(rows) >= config.daily:
        return 'daily_limit'
    if rows and time.time()-max(r[0] for r in rows) < config.cooldown:
        return 'cooldown'
    return None


class Inbox:
    def __init__(self, provider, friends, started, primary=False):
        self.provider, self.friends, self.started = provider, friends, started
        self.primary = primary
        self.considered = set()
        self.snapshot = None

    def poll(self):
        c = self.provider.client
        c.request_budget = 3
        events = []
        self.skipped = {}
        def skip(reason):
            self.skipped[reason] = self.skipped.get(reason, 0)+1
        if self.primary:
            threads, _ = c.direct_threads_chunk(box='primary', thread_message_limit=1)
        else:
            threads = c.direct_threads(amount=3, thread_message_limit=1)
        for thread in threads:
            if self.primary and (getattr(thread, 'pending', True) or getattr(thread, 'folder', None) != 0):
                skip('not_primary_or_pending')
                continue
            if (not self.primary and len(thread.users) != 1) or not thread.messages:
                skip('group_or_empty')
                continue
            m = max(thread.messages, key=lambda x: x.timestamp)
            key = 'dm:' + str(m.id)
            if not m.user_id or str(m.user_id) == str(c.user_id):
                skip('own_message')
                continue
            if (not self.primary and str(m.user_id) not in self.friends) or not m.text or key in self.considered:
                skip('not_allowed_or_no_text_or_considered')
                continue
            ts = timestamp(m.timestamp)
            if ts < self.started:
                skip('before_session_start')
                continue
            events.append(Event(key, 'dm', str(m.user_id), str(thread.id), m.text[:1000], ts))
        self.snapshot = {'account': {'id': str(c.user_id)}, 'capabilities': ['reply_dm'], 'events': events}
        return events

    def observe(self):
        return self.snapshot

    def execute(self, action, event):
        return self.provider.execute(action, event)


def run_chat(config, provider, journal, owner_only=False):
    import msvcrt
    if config.provider != 'private':
        raise ConfigurationError('chat currently requires IG_PROVIDER=private.')
    owner = load_owner(config, provider.client.user_id)
    if not owner:
        raise ConfigurationError('First run bind-owner with OWNER_USERNAME configured.')
    config.friends = {owner['user_id']}
    config.allow = {'reply_dm'}
    config.cooldown = 0  # Only this explicit short session; .env remains unchanged.
    scope = 'private:' + str(provider.client.user_id)
    started = time.time()
    inbox = Inbox(provider, config.friends, started, primary=not owner_only)
    active, next_poll = False, 0
    last_report = 0
    journal.log(status='chat_started', owner_only=owner_only, mode='live' if config.live else 'dry-run')
    print('PAUSED | S=start/resume P=pause Q=quit | 5s polling | 10-minute session')
    print('Scope: ' + ('owner only' if owner_only else 'PRIMARY inbox, including GROUP chats'))
    print('Only new text DMs since launch; latest message per chat. Mode: ' + ('LIVE' if config.live else 'DRY RUN'))
    try:
        while time.time()-started < 600:
            if (config.state_dir/'STOP').exists():
                break
            while msvcrt.kbhit():
                key = msvcrt.getwch().lower()
                if key == 'q':
                    return 0
                if key in {'s', 'p'}:
                    active = key == 's'
                    print('ACTIVE' if active else 'PAUSED', flush=True)
                    journal.log(status='chat_active' if active else 'chat_paused')
            if active and time.monotonic() >= next_poll:
                blocked = available(config, journal, scope)
                if blocked:
                    print(blocked)
                    return 0
                events = inbox.poll()
                if time.monotonic()-last_report >= 30:
                    info = dict(status='chat_poll', candidates=len(events), skipped=inbox.skipped, remaining_seconds=max(0, int(600-(time.time()-started))))
                    print(json.dumps(info), flush=True)
                    journal.log(**info)
                    last_report = time.monotonic()
                # Process queued pause/quit before starting the model or a send.
                if msvcrt.kbhit():
                    continue
                fresh = [e for e in events if not journal.seen(scope, e.id)]
                if fresh:
                    # One room per model call: do not mix private/group conversations.
                    fresh = [min(fresh, key=lambda e: e.timestamp)]
                    inbox.snapshot['events'] = fresh
                    if not owner_only:
                        config.friends = {e.actor for e in fresh}
                    journal.log(status='chat_model_started', event_id=fresh[0].id)
                    print('Generating reply...', flush=True)
                    result = cycle(config, inbox, journal)
                    print(json.dumps(result, ensure_ascii=False))
                    if result['status'] in {'noop', 'dry_run'}:
                        inbox.considered.update(e.id for e in fresh)
                    elif result.get('event_id'):
                        inbox.considered.add(result['event_id'])
                    if result['status'] in {'unresolved_attempt', 'daily_limit', 'stopped'}:
                        return 0
                next_poll = time.monotonic()+5
            time.sleep(0.1)
        return 0
    finally:
        journal.log(status='chat_ended', elapsed_seconds=round(time.time()-started))
        print('Chat stopped. Polling is off. Restart the command to receive more DMs.', flush=True)
