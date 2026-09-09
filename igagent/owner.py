"""Local owner identity. DM text never grants administrative authority."""
import json
import os
import re
from .core import ConfigurationError


def bind_owner(config, provider):
    if config.provider != 'private':
        raise ConfigurationError('Owner lookup currently supports the private provider only.')
    username = os.getenv('OWNER_USERNAME', '').strip().lstrip('@')
    if not re.fullmatch(r'[A-Za-z0-9_.]{1,30}', username):
        raise ConfigurationError('Set OWNER_USERNAME to the Instagram username in .env.')
    user = provider.client.user_info_by_username_v1(username)
    if user.username.lower() != username.lower():
        raise ConfigurationError('Owner username lookup did not match.')
    if str(user.pk) == str(provider.client.user_id):
        raise ConfigurationError('Owner and experimental account must be different accounts.')
    owner = {'username': user.username, 'user_id': str(user.pk),
             'account_id': str(provider.client.user_id), 'provider': config.provider}
    config.state_dir.mkdir(parents=True, exist_ok=True)
    path = config.state_dir / 'owner.json'
    # A failed write cannot leave a partially bound owner.
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(owner, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    return owner


def load_owner(config, account_id):
    path = config.state_dir / 'owner.json'
    if not path.exists():
        return None
    owner = json.loads(path.read_text(encoding='utf-8'))
    if owner.get('provider') != config.provider or owner.get('account_id') != str(account_id):
        return None
    if owner.get('username', '').lower() != os.getenv('OWNER_USERNAME', '').lstrip('@').lower():
        return None
    if not str(owner.get('user_id', '')).isdigit():
        raise ConfigurationError('Invalid owner identity. Run bind-owner again.')
    return owner
