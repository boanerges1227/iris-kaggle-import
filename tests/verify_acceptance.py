"""Verify each labeled result from the IRIS acceptance session separately."""
import json
import sys


def parse_results(log):
    """Collect JSON following CASE markers while ignoring download messages."""
    results = {}
    case = None
    for line in log.splitlines():
        line = line.strip()
        if line.startswith('CASE:'):
            case = line[5:]
        elif case and line.startswith('{'):
            results[case] = json.loads(line)
            case = None
    return results


def check_results(results):
    """Return the names of cases that did not meet their own expectations."""
    predicates = {
        'import': lambda r: r.get('status') == 'success' and r.get('rowsWritten') == 782 and len(r.get('tables', [])) == 5,
        'info': lambda r: '2015.csv' in r.get('files', []),
        'invalid': lambda r: r.get('status') == 'error' and 'invalid handle' in r.get('error', ''),
        'pinned': lambda r: r.get('status') == 'success' and r.get('pinned') is True,
        'fail': lambda r: r.get('status') == 'error' and 'already exists' in r.get('error', ''),
        'limit': lambda r: r.get('status') == 'success' and len(r.get('tables', [])) == 5 and all(t.get('rows') == 10 for t in r['tables']),
    }
    return [name for name, predicate in predicates.items() if name not in results or not predicate(results[name])]


def main(path):
    """Print per-case results and return a nonzero exit status on failure."""
    with open(path, encoding='utf-8') as file:
        results = parse_results(file.read())
    failed = check_results(results)
    for name in ('import', 'info', 'invalid', 'pinned', 'fail', 'limit'):
        print(f"  {'FAIL' if name in failed else 'PASS'}: {name}")
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
