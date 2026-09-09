import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, quote

from .core import ConfigurationError, Event, flag, request_json


def required(name):
    value = os.getenv(name, '')
    if not value:
        raise ValueError(name + '_required')
    return value


def timestamp(value):
    if isinstance(value, datetime):
        return value.timestamp()
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def assets():
    path = Path('assets.json')
    if not path.exists():
        return []
    items = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(items, list) or len(items) > 10:
        raise ValueError('invalid_assets')
    return [Event('asset:' + str(a['id']), 'asset', 'self', str(a['id']),
                  str(a['description'])[:1000], time.time()) for a in items]


def asset_source(event, key):
    items = json.loads(Path('assets.json').read_text(encoding='utf-8-sig'))
    a = next(a for a in items if str(a['id']) == event.target)
    return a[key]


class Mock:
    def observe(self):
        return {'account': {'id': 'mock-account', 'username': 'ai_experiment'},
                'capabilities': ['reply_dm', 'reply_comment', 'comment', 'like', 'publish_photo'],
                'events': [Event('dm:demo-1', 'dm', 'friend-1', 'thread-1',
                                 '안녕! 오늘은 어떤 실험을 하고 있어?', time.time()),
                           Event('comment:demo-2', 'comment', 'friend-1', 'comment-1',
                                 '사진 분위기 좋다!', time.time(), 'media-1'),
                           Event('feed:demo-3', 'feed', 'friend-1', 'media-2',
                                 '산책 중 만난 고양이', time.time())] + assets()}

    def execute(self, action, event):
        raise RuntimeError('mock_never_executes')


class Graph:
    """Official Instagram Login path; deliberately separate from Facebook Login."""
    def __init__(self):
        self.token = required('IG_GRAPH_TOKEN')
        self.account = required('IG_GRAPH_USER_ID')
        version = required('IG_GRAPH_VERSION')
        if not re.fullmatch(r'v\d+\.\d+', version) or not self.account.isdigit():
            raise ValueError('invalid_graph_version_or_user_id')
        self.base = 'https://graph.instagram.com/' + version
        self.dm = flag('GRAPH_ENABLE_DM')

    def call(self, path, params=None, body=None):
        url = self.base + '/' + '/'.join(quote(p, safe='') for p in path.split('/'))
        if params:
            url += '?' + urlencode(params)
        return request_json(url, self.token, body)

    def observe(self):
        account = self.call(self.account, {'fields': 'id,username'})
        events = []
        media = self.call(self.account + '/media', {'fields': 'id,caption,timestamp', 'limit': 3})
        for post in media.get('data', [])[:3]:
            comments = self.call(post['id'] + '/comments',
                                 {'fields': 'id,text,from,timestamp', 'limit': 5})
            for c in comments.get('data', [])[:5]:
                actor = str(c.get('from', {}).get('id', ''))
                if actor and actor != str(account['id']):
                    events.append(Event('comment:' + c['id'], 'comment', actor, c['id'],
                                        c.get('text', '')[:1000], timestamp(c['timestamp']), post['id']))
        if self.dm:
            conversations = self.call(self.account + '/conversations', {'platform': 'instagram', 'limit': 3})
            for conv in conversations.get('data', [])[:3]:
                messages = self.call(conv['id'] + '/messages', {'fields': 'id,created_time', 'limit': 1})
                for item in messages.get('data', [])[:1]:
                    m = self.call(item['id'], {'fields': 'id,created_time,from,to,message'})
                    actor = str(m.get('from', {}).get('id', ''))
                    # Latest outgoing messages suppress automated re-replies.
                    if actor and actor != str(account['id']):
                        events.append(Event('dm:' + m['id'], 'dm', actor, actor,
                                            m.get('message', '')[:1000], timestamp(m['created_time'])))
        return {'account': {'id': str(account['id']), 'username': account.get('username', '')},
                'capabilities': ['reply_comment', 'publish_photo'] + (['reply_dm'] if self.dm else []),
                'events': events + assets()}

    def execute(self, action, event):
        if action.kind == 'reply_comment':
            self.call(event.target + '/replies', body={'message': action.text})
        elif action.kind == 'reply_dm' and self.dm:
            self.call(self.account + '/messages', body={'recipient': {'id': event.target},
                                                       'message': {'text': action.text}})
        elif action.kind == 'publish_photo':
            url = asset_source(event, 'image_url')
            if not url.startswith('https://'):
                raise ValueError('asset_requires_https')
            container = self.call(self.account + '/media', body={'image_url': url, 'caption': action.text})
            # Bounded wait for Meta's media processing; no repeated POSTs.
            for _ in range(10):
                status = self.call(container['id'], {'fields': 'status_code'})['status_code']
                if status == 'FINISHED':
                    self.call(self.account + '/media_publish', body={'creation_id': container['id']})
                    return
                if status in {'ERROR', 'EXPIRED'}:
                    raise RuntimeError('container_failed')
                time.sleep(2)
            raise RuntimeError('container_not_ready')
        else:
            raise ValueError('unsupported_graph_action')


class Private:
    def __init__(self):
        if not flag('ACK_PRIVATE_API_RISK'):
            raise ValueError('ACK_PRIVATE_API_RISK_required_even_for_reads')
        from .private_client import make_client, enforce_no_retries
        # No password login in the loop and no challenge bypass or proxy rotation.
        self.client = make_client()
        self.client.load_settings(required('IG_SESSION_FILE'))
        enforce_no_retries(self.client)
        if not self.client.user_id:
            raise ValueError('session_has_no_user_id')

    def observe(self):
        c = self.client
        c.request_budget = 20
        me = str(c.user_id)
        events = []
        for thread in c.direct_threads(amount=3, thread_message_limit=1):
            # Group threads intentionally excluded, including unknown membership.
            if len(thread.users) != 1 or not thread.messages:
                continue
            m = max(thread.messages, key=lambda m: m.timestamp)
            if m.user_id and str(m.user_id) != me and m.text:
                events.append(Event('dm:' + str(m.id), 'dm', str(m.user_id), str(thread.id),
                                    m.text[:1000], timestamp(m.timestamp)))
        for media in c.user_medias_v1(c.user_id, amount=3):
            for comment in c.media_comments(media.pk, amount=5):
                if str(comment.user.pk) != me:
                    events.append(Event('comment:' + str(comment.pk), 'comment', str(comment.user.pk),
                                        str(comment.pk), comment.text[:1000], timestamp(comment.created_at_utc), str(media.pk)))
        if flag('PRIVATE_ENABLE_FEED'):
            # One timeline page. Handle normal media and feed_items wrappers.
            feed = c.get_timeline_feed()
            raw_items = feed.get('feed_items', feed.get('items', []))
            for raw in raw_items[:10]:
                m = raw.get('media_or_ad', raw)
                actor = str(m.get('user', {}).get('pk', ''))
                if m.get('pk') and actor and actor != me:
                    events.append(Event('feed:' + str(m['pk']), 'feed', actor, str(m['pk']),
                                        (m.get('caption') or {}).get('text', '')[:1000],
                                        float(m.get('taken_at', 0))))
        return {'account': {'id': me, 'username': 'private-experiment'},
                'capabilities': ['reply_dm', 'reply_comment', 'comment', 'like', 'publish_photo'],
                'events': events + assets()}

    def execute(self, action, event):
        c = self.client
        c.request_budget = 10
        if action.kind == 'reply_dm':
            c.direct_send(action.text, thread_ids=[int(event.target)])
        elif action.kind == 'reply_comment':
            c.media_comment(event.media, action.text, replied_to_comment_id=int(event.target))
        elif action.kind == 'comment':
            c.media_comment(event.target, action.text)
        elif action.kind == 'like':
            if not c.media_like(event.target):
                raise RuntimeError('like_not_confirmed')
        elif action.kind == 'publish_photo':
            root = Path('media').resolve()
            path = (root / asset_source(event, 'file')).resolve()
            if not path.is_relative_to(root) or path.suffix.lower() not in {'.jpg', '.jpeg'} or not path.is_file():
                raise ValueError('asset_requires_jpeg_inside_media')
            # Upstream photo_upload repeats configuration; use one upload/configure pair.
            upload_id, width, height = c.photo_rupload(path)
            if not c.photo_configure(upload_id, width, height, caption=action.text):
                raise RuntimeError('photo_configuration_unconfirmed')
        else:
            raise ValueError('unsupported_private_action')


def private_login():
    if not flag('ACK_PRIVATE_API_RISK'):
        raise ConfigurationError('Private login is disabled. Set ACK_PRIVATE_API_RISK=true in .env to acknowledge the private API risk.')
    from getpass import getpass
    from .private_client import make_client, enforce_no_retries
    c = make_client(strict=False)
    session = Path(required('IG_SESSION_FILE'))
    session.parent.mkdir(parents=True, exist_ok=True)
    if session.exists():
        c.load_settings(session)
    enforce_no_retries(c)
    username = os.getenv('IG_USERNAME') or input('Instagram username: ')
    password = os.getenv('IG_PASSWORD') or getpass('Instagram password (hidden): ')
    code = getpass('2FA code if enabled, otherwise Enter (hidden): ')
    if not c.login(username, password, verification_code=code):
        raise RuntimeError('login_failed')
    c.dump_settings(session)
    if os.name != 'nt':
        session.chmod(0o600)
    print('Session saved locally. Never share this file.')


def create_provider(name):
    return {'mock': Mock, 'graph': Graph, 'private': Private}[name]()
