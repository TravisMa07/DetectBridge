"""Run repository hygiene checks against tracked files using the CI tool configuration."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ('content', 'markdown', 'workflows', 'secrets', 'tests')


def tracked(root):
    result = subprocess.run(['git', 'ls-files', '-z'], cwd=root, check=True, capture_output=True)
    return [Path(p.decode()) for p in result.stdout.split(b'\0') if p]


def yaml_load(text):
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError('Missing PyYAML: python3 -m pip install -r tools/hygiene/requirements.txt') from exc

    class UniqueLoader(yaml.SafeLoader):
        pass

    UniqueLoader.yaml_implicit_resolvers = {
        key: [(tag, regex) for tag, regex in values if tag != 'tag:yaml.org,2002:bool']
        for key, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }
    UniqueLoader.add_implicit_resolver('tag:yaml.org,2002:bool', re.compile(r'^(?:true|false)$', re.I), list('tTfF'))

    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if key in result:
                raise ValueError(f'duplicate YAML key: {key}')
            result[key] = loader.construct_object(value_node)
        return result

    UniqueLoader.add_constructor('tag:yaml.org,2002:map', mapping)
    return yaml.load(text, Loader=UniqueLoader)


def without_fences(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is None:
            lines.append(line)
    return '\n'.join(lines)


def anchors(text):
    result, counts = set(), {}
    for line in without_fences(text).splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)(?:\s+#+)?$', line)
        if match:
            title = re.sub(r'<[^>]*>', '', match.group(1)).lower()
            title = re.sub(r'[^\w\-\s]', '', title).replace(' ', '-')
            number = counts.get(title, 0)
            counts[title] = number + 1
            result.add(title + (f'-{number}' if number else ''))
    result.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)', text))
    return result


def form_errors(data, path):
    errors = []
    if not isinstance(data, dict) or not all(data.get(k) for k in ('name', 'description', 'body')):
        return [f'{path}: issue form needs name, description, body']
    if not isinstance(data['body'], list):
        return [f'{path}: body must be a list']
    ids = set()
    for item in data['body']:
        if not isinstance(item, dict) or item.get('type') not in ('markdown', 'textarea', 'input', 'dropdown', 'checkboxes'):
            errors.append(f'{path}: invalid form item type')
            continue
        if item['type'] == 'markdown':
            continue
        ident = item.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', ident) or ident in ids:
            errors.append(f'{path}: invalid or duplicate form id')
        else:
            ids.add(ident)
        if not item.get('attributes', {}).get('label'):
            errors.append(f'{path}: input missing label')
        if item.get('validations', {}).get('required') is not True:
            errors.append(f'{path}: planned issue fields must be required')
    return errors


def workflow_errors(data, path):
    if not isinstance(data, dict) or not isinstance(data.get('jobs'), dict) or 'on' not in data:
        return [f'{path}: workflow needs triggers and jobs']
    errors = []
    if data.get('permissions') != {'contents': 'read'}:
        errors.append(f'{path}: expected read-only contents permission')
    events = data['on']
    if 'pull_request_target' in events:
        errors.append(f'{path}: privileged PR event forbidden')
    for job in data['jobs'].values():
        if job.get('permissions') not in (None, {'contents': 'read'}):
            errors.append(f'{path}: elevated job permission forbidden')
        if not isinstance(job.get('timeout-minutes'), int):
            errors.append(f'{path}: missing job timeout')
        for step in job.get('steps', []):
            use = step.get('uses', '')
            if use and not re.fullmatch(r'[\w.-]+/[\w./-]+@[0-9a-f]{40}', use):
                errors.append(f'{path}: action must use full commit SHA')
            if use.startswith('actions/checkout@') and step.get('with', {}).get('persist-credentials') is not False:
                errors.append(f'{path}: checkout must disable persisted credentials')
    return errors


def content_errors(root, files):
    errors = []
    for rel in files:
        path = root / rel
        if path.is_symlink():
            errors.append(f'{rel}: tracked symlinks are not supported by hygiene')
            continue
        if not path.exists():  # a tracked file intentionally deleted in the working tree
            continue
        try:
            text = path.read_bytes().decode('utf-8')
        except UnicodeDecodeError:
            errors.append(f'{rel}: expected UTF-8 text'); continue
        if '\r' in text or (text and not text.endswith('\n')):
            errors.append(f'{rel}: expected LF and final newline')
        if rel.name != 'LICENSE' and any(line.rstrip() != line for line in text.splitlines()):
            errors.append(f'{rel}: trailing whitespace')
        if rel.suffix in ('.json', '.yml', '.yaml'):
            try:
                data = json.loads(text) if rel.suffix == '.json' else yaml_load(text)
                if rel.parent.as_posix() == '.github/ISSUE_TEMPLATE' and rel.name != 'config.yml':
                    errors.extend(form_errors(data, rel))
                if rel.parent.as_posix() == '.github/workflows':
                    errors.extend(workflow_errors(data, rel))
            except RuntimeError:
                raise
            except Exception as exc:
                errors.append(f'{rel}: invalid configuration ({type(exc).__name__})')
        if rel.suffix != '.md':
            continue
        body = without_fences(text)
        links = re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', body)
        links += re.findall(r'^\s*\[[^\]]+\]:\s*(\S+)', body, re.M)
        for link in links:
            link = link.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', link) or link.startswith('//'):
                continue
            filepart, sep, fragment = link.partition('#')
            dest = (root / unquote(filepart).lstrip('/')) if filepart.startswith('/') else path.parent / unquote(filepart)
            if not filepart:
                dest = path
            if not dest.exists():
                errors.append(f'{rel}: broken relative link {link}')
            elif sep and fragment and dest.suffix == '.md' and unquote(fragment) not in anchors(dest.read_text()):
                errors.append(f'{rel}: missing heading anchor {link}')
    return errors


def native(name):
    path = ROOT / '.cache/hygiene/bin' / name
    if not path.is_file():
        raise RuntimeError(f'Missing {name}: python3 tools/install_hygiene.py --tool {name}')
    return str(path)


def run(command, **kwargs):
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', choices=CHECKS, action='append', help='Repeat to select checks; default: all')
    args = parser.parse_args()
    files = tracked(ROOT)
    try:
        for check in args.check or CHECKS:
            print(f'Checking {check}...', flush=True)
            if check == 'content':
                errors = content_errors(ROOT, files)
                if errors:
                    raise RuntimeError('\n'.join(errors))
            elif check == 'markdown':
                binary = ROOT / 'tools/hygiene/node_modules/.bin/markdownlint-cli2'
                if not binary.exists():
                    raise RuntimeError('Missing markdownlint-cli2: npm ci --prefix tools/hygiene')
                run([str(binary), *[p.as_posix() for p in files if p.suffix == '.md' and (ROOT / p).exists()]])
            elif check == 'workflows':
                run([native('actionlint'), '-shellcheck=', '-pyflakes='])
            elif check == 'secrets':
                binary = native('gitleaks')
                run([binary, 'git', '--redact', '--no-banner', '--log-opts=--all', '.'])
                with tempfile.TemporaryDirectory(prefix='detectbridge-scan-') as folder:
                    for rel in files:
                        source = ROOT / rel
                        if source.is_file() and not source.is_symlink():
                            dest = Path(folder) / rel
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(source, dest)
                    run([binary, 'dir', '--redact', '--no-banner', folder])
            elif check == 'tests':
                run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tools/tests', '-v'])
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    print('PASS: selected hygiene checks')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
