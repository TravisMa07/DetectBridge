"""Owner-run administration only. Default reports state; --apply performs selected setup."""
import argparse
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / 'tools/hygiene/repository-policy.json').read_text())
REPO = POLICY['repository']
BASE = f'repos/{REPO}'


def api(path, method='GET', body=None):
    args = ['gh', 'api', path, '--method', method]
    if body is not None:
        args += ['--input', '-']
    result = subprocess.run(args, input=json.dumps(body) if body is not None else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def pages(path):
    result, page = [], 1
    separator = '&' if '?' in path else '?'
    while True:
        items = api(f'{path}{separator}per_page=100&page={page}')
        result.extend(items)
        if len(items) < 100:
            return result
        page += 1


def tracking():
    roadmap = (ROOT / 'docs/roadmap.md').read_text()
    milestone_specs = re.findall(r'^\| (M\d+ — [^|]+) \| [^|]+ \| ([^|]+) \|$', roadmap, re.M)
    milestone_specs += [
        ('Expansion — Attack chains', 'Define and qualify deterministic event-time correlation with evidence linkage.'),
        ('Expansion — AI assistance', 'Qualify optional local and hosted assistance with human approval and core-pipeline isolation.'),
        ('Expansion — Selective forwarding', 'Qualify shadow policies, evidence retention and coverage-aware routing.'),
        ('Expansion — Distributed deployment', 'Qualify shared state, scaling, replication, recovery and upgrades separately.')]
    existing = {m['title']: m for m in pages(BASE + '/milestones?state=all')}
    for title, description in milestone_specs:
        if title not in existing:
            existing[title] = api(BASE + '/milestones', 'POST', {'title': title, 'description': description})
    labels = {label['name'] for label in pages(BASE + '/labels')}
    if 'blocked' not in labels:
        api(BASE + '/labels', 'POST', {'name': 'blocked', 'color': 'b60205', 'description': 'Blocked by an explicit dependency or access requirement'})
    issues = [i for i in pages(BASE + '/issues?state=all') if 'pull_request' not in i]
    by_id = {}
    for issue in issues:
        match = re.match(r'^\[(P\d{2})\]', issue['title'])
        if match:
            if match[1] in by_id:
                raise RuntimeError(f'Ambiguous duplicate planning ID {match[1]}; resolve manually')
            by_id[match[1]] = issue
    created = []
    for match in re.finditer(r'^### (P\d{2}) — ([^\n]+)\n(.*?)(?=^### |^## |\Z)', roadmap, re.M | re.S):
        ident, title, body = match.groups()
        if ident in by_id:
            continue  # preserve existing user changes, state and milestone assignments
        sections = list(re.finditer(r'^## (M\d+ — [^\n]+)', roadmap[:match.start()], re.M))
        milestone = existing[sections[-1][1]]['number']
        state = 'In progress' if ident == 'P01' else 'Backlog'
        issue_body = f'Planning ID: {ident}\n\nInitial workflow status: {state}. The project Status field becomes authoritative once configured.\n\n{body.strip()}\n'
        by_id[ident] = api(BASE + '/issues', 'POST', {'title': f'[{ident}] {title}', 'body': issue_body, 'milestone': milestone})
        created.append(ident)
    for ident in created:
        issue = by_id[ident]
        body = issue['body']
        match = re.search(r'- Depends on: ([^\n]+)', body)
        if match:
            references = re.findall(r'P\d{2}', match[1])
            if references:
                body += '\nDependency issues: ' + ', '.join(f'#{by_id[ref]["number"]} ({ref})' for ref in references) + '.\n'
                api(BASE + '/issues/' + str(issue['number']), 'PATCH', {'body': body})
    print(json.dumps({'milestones': len(existing), 'created_issues': len(created), 'issues': {k: v['number'] for k,v in by_id.items()}}, indent=2))


def policies():
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    checks = api(f'{BASE}/commits/{sha}/check-runs')['check_runs']
    successes = [c for c in checks if c['name'] == 'required-checks' and c['conclusion'] == 'success' and c['app']['id'] == 15368]
    if not successes:
        raise RuntimeError('Refusing policy changes before GitHub Actions required-checks succeeds on local HEAD')
    api(BASE, 'PATCH', POLICY['settings'])
    api(BASE + '/actions/permissions/workflow', 'PUT', POLICY['workflow_permissions'])
    api(BASE + '/private-vulnerability-reporting', 'PUT')
    rulesets = [r for r in pages(BASE + '/rulesets') if r['name'] == POLICY['ruleset']['name']]
    if len(rulesets) > 1:
        raise RuntimeError('Multiple matching rulesets; resolve ambiguity manually')
    if rulesets:
        current = api(BASE + '/rulesets/' + str(rulesets[0]['id']))
        fields = ('name', 'target', 'enforcement', 'bypass_actors', 'conditions', 'rules')
        if any(current.get(k) != POLICY['ruleset'].get(k) for k in fields):
            raise RuntimeError('Existing ruleset differs; review user changes before updating it')
    else:
        api(BASE + '/rulesets', 'POST', POLICY['ruleset'])
    readback()


def readback():
    repo = api(BASE)
    print(json.dumps({'settings': {k: repo[k] for k in POLICY['settings']},
                      'workflow_permissions': api(BASE + '/actions/permissions/workflow'),
                      'private_reporting': api(BASE + '/private-vulnerability-reporting'),
                      'rulesets': [api(BASE + '/rulesets/' + str(r['id'])) for r in pages(BASE + '/rulesets')]}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', choices=('tracking', 'policies'))
    args = parser.parse_args()
    try:
        if args.apply == 'tracking':
            tracking()
        elif args.apply == 'policies':
            policies()
        else:
            readback()
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(getattr(exc, 'stderr', '') or str(exc))
        raise SystemExit(1)
