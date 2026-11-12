"""Fail closed unless every required job explicitly succeeded."""
import json
import os

EXPECTED = {'repository-hygiene', 'secret-scan'}


def gate_passes(needs):
    return (isinstance(needs, dict) and set(needs) == EXPECTED
            and all(isinstance(item, dict) and item.get('result') == 'success'
                    for item in needs.values()))


if __name__ == '__main__':
    try:
        passed = gate_passes(json.loads(os.environ.get('NEEDS_JSON', '{}')))
    except (ValueError, TypeError):
        passed = False
    print('Required checks passed.' if passed else 'Required checks failed or did not complete.')
    raise SystemExit(0 if passed else 1)
