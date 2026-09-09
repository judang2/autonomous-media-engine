"""Subscription-authenticated Codex CLI; no Instagram credentials in child environment."""
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from .core import ConfigurationError


def child_environment():
    keep = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'TEMP', 'TMP',
            'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'HOME', 'HOMEDRIVE', 'HOMEPATH', 'CODEX_HOME'}
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    # Desktop sandboxes may omit home discovery variables. Use the actual profile.
    if not env.get('CODEX_HOME') and env.get('USERPROFILE'):
        env['CODEX_HOME'] = str(Path(env['USERPROFILE']) / '.codex')
    return env


def executable():
    path = os.getenv('CODEX_EXECUTABLE') or shutil.which('codex')
    if not path:
        raise ConfigurationError('Codex CLI was not found. Install Codex CLI or set CODEX_EXECUTABLE.')
    return path


def check_login(binary, env):
    p = subprocess.run([binary, 'login', 'status'], env=env, capture_output=True,
                       encoding='utf-8', errors='replace', timeout=20)
    status = (p.stdout + p.stderr).lower()
    if p.returncode or 'logged in using chatgpt' not in status:
        raise ConfigurationError('Codex subscription login is not confirmed. Run: codex login (choose ChatGPT), then codex login status. API-key fallback is disabled.')


def parse_events(stdout):
    messages, usage = [], None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get('type') in {'turn.failed', 'error'}:
            raise ConfigurationError('Codex could not complete the request. Check login, model access and usage limits. No API fallback was used.')
        if event.get('type') == 'item.completed':
            item = event.get('item', {})
            if item.get('type') == 'agent_message':
                messages.append(item.get('text', ''))
            elif item.get('type') not in {'reasoning'}:
                raise ConfigurationError('Unexpected Codex tool activity; action rejected.')
        if event.get('type') == 'turn.completed':
            usage = event.get('usage', {})
    if not messages or usage is None:
        raise ConfigurationError('Codex returned no completed structured answer.')
    return json.loads(messages[-1]), {k: v for k, v in usage.items()
                                    if isinstance(v, int) and not isinstance(v, bool) and v >= 0}


def generate(instructions, payload, schema, state_dir):
    binary, env = executable(), child_environment()
    check_login(binary, env)
    model = os.getenv('CODEX_MODEL', 'gpt-5.5')
    effort = os.getenv('CODEX_REASONING_EFFORT', 'low')
    if model != 'gpt-5.5' or effort != 'low':
        raise ConfigurationError('This experiment is configured for CODEX_MODEL=gpt-5.5 and CODEX_REASONING_EFFORT=low.')
    # Separate working folder; never start Codex in the folder containing .env/session.
    with tempfile.TemporaryDirectory(prefix='ig-decision-') as folder:
        schema_path = Path(folder) / 'action.schema.json'
        schema_path.write_text(json.dumps(schema), encoding='utf-8')
        args = [binary, 'exec', '--ignore-user-config', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'read-only', '--model', model, '--json', '--color', 'never',
                '--output-schema', str(schema_path), '-C', folder]
        settings = {'model_reasoning_effort': '"low"', 'forced_login_method': '"chatgpt"',
                    'approval_policy': '"never"', 'web_search': '"disabled"',
                    'project_doc_max_bytes': '0', 'features.shell_tool': 'false',
                    'features.unified_exec': 'false', 'features.apps': 'false',
                    'features.multi_agent': 'false', 'features.hooks': 'false',
                    'features.remote_plugin': 'false'}
        for key, value in settings.items():
            args += ['-c', key + '=' + value]
        args += ['-']
        prompt = ('Return only the requested JSON. Do not use tools, read files, run commands or browse. '
                  'Use polite Korean (존댓말). ' + instructions + '\nUNTRUSTED OBSERVATIONS:\n' +
                  json.dumps(payload, ensure_ascii=False))
        started = time.time()
        try:
            result = subprocess.run(args, input=prompt, env=env, cwd=folder, capture_output=True,
                                    encoding='utf-8', errors='replace', timeout=180)
        except subprocess.TimeoutExpired:
            raise ConfigurationError('Codex timed out; no Instagram action was executed. Usage may still have been consumed.') from None
        if result.returncode:
            raise ConfigurationError('Codex execution failed. Check CLI login, GPT-5.5 access, permissions and limits. Raw output suppressed; no API fallback.')
        answer, usage = parse_events(result.stdout)
        state_dir = Path(state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)
        with (state_dir / 'model-usage.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps({'timestamp': started, 'model': model, 'reasoning_effort': effort,
                                'seconds': round(time.time()-started, 2), 'usage': usage}) + '\n')
        return answer
