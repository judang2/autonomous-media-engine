import argparse
import json
import time
import sys

from .core import Config, ConfigurationError, Journal, cycle, load_env
from .providers import create_provider, private_login


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Instagram experiment; dry-run by default')
    parser.add_argument('command', choices=['run', 'observe', 'login-private', 'bind-owner', 'chat'], nargs='?', default='run')
    parser.add_argument('--owner-only', action='store_true', help='Only consider DMs from the locally bound owner')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--cycles', type=int, default=1)
    parser.add_argument('--interval', type=int, default=1800)
    args = parser.parse_args()
    journal = None
    try:
        load_env()
        if args.command == 'login-private':
            private_login()
            return 0
        config = Config.env(args.live)
        if not 1 <= args.cycles <= 48 or args.interval < 600:
            raise ValueError('cycles_1_to_48_interval_at_least_600')
        journal = Journal(config.state_dir)
        if (config.state_dir / 'STOP').exists():
            print('{"status":"stopped"}')
            return 0
        provider = create_provider(config.provider)
        if args.command == 'bind-owner':
            from .owner import bind_owner
            print(json.dumps({'status': 'owner_bound', **bind_owner(config, provider)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == 'chat':
            from .chat import run_chat
            return run_chat(config, provider, journal, owner_only=args.owner_only)
        if args.owner_only:
            from .owner import load_owner
            if config.provider != 'private':
                raise ConfigurationError('--owner-only currently requires the private provider.')
            owner = load_owner(config, provider.client.user_id)
            if not owner:
                raise ConfigurationError('First run: python -m igagent bind-owner')
            config.friends = {owner['user_id']}
            config.allow = {'reply_dm'}
            original_observe = provider.observe
            def owner_observe():
                snapshot = original_observe()
                snapshot['events'] = [e for e in snapshot['events'] if e.kind == 'dm' and e.actor == owner['user_id']]
                return snapshot
            provider.observe = owner_observe
        if args.command == 'observe':
            s = provider.observe()
            # IDs are shown so the operator can configure the friend allowlist.
            print(json.dumps({'account': s['account'], 'capabilities': s['capabilities'],
                              'events': [{'id': e.id, 'kind': e.kind, 'actor': e.actor} for e in s['events']]},
                             ensure_ascii=False, indent=2))
            return 0
        for i in range(args.cycles):
            result = cycle(config, provider, journal)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            if result['status'] in {'stopped', 'unresolved_attempt'}:
                break
            if i + 1 < args.cycles:
                for _ in range(args.interval):
                    if (config.state_dir / 'STOP').exists():
                        return 0
                    time.sleep(1)
        return 0
    except ConfigurationError as exc:
        print('Configuration error: ' + str(exc))
        return 1
    except KeyboardInterrupt:
        print('Stopped. Check journal for pending attempts before restarting.')
        return 130
    except Exception as exc:
        # Exception messages/tracebacks can contain URLs, tokens or private content.
        name = type(exc).__name__
        if journal:
            journal.log(status='error', error_type=name)
        print('Stopped: ' + name + '. Check configuration, credentials and README troubleshooting. Raw error suppressed.')
        return 1
    finally:
        if journal:
            journal.db.close()


if __name__ == '__main__':
    raise SystemExit(main())
