#!/usr/bin/env python3
"""Replay the saved lifetime regression (unsafe variant optionally uses ~1 GiB)."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-unsafe', action='store_true')
    args = parser.parse_args()
    fixture = json.loads((ROOT/'records/dce/lifetime-before-fix.json').read_text())
    with tempfile.TemporaryDirectory(prefix='dce-lifetime-replay-') as directory:
        directory = Path(directory)
        data, program, schema, candidate = (directory/name for name in ('data.json', 'program.mini', 'schema.json', 'candidate.mini'))
        data.write_text(json.dumps({'t': {'columns': [{'name': 'x', 'type': 'INT'}], 'rows': [[1]]*fixture['rows']}}))
        program.write_text(fixture['program'])
        schema.write_bytes(subprocess.check_output([str(ROOT/'bin/minivm'), '--schema', str(data)], timeout=10))
        current = subprocess.check_output([str(ROOT/'optimize'), str(program), str(schema)], timeout=60)
        executions = [('original', fixture['program'].encode()), ('current', current)]
        if args.include_unsafe:
            executions.append(('unsafe_before_fix', fixture['candidate'].encode()))
        results = {}
        for name, source in executions:
            candidate.write_bytes(source)
            run = subprocess.run([str(ROOT/'bin/minivm'), str(candidate), str(data)], capture_output=True, timeout=20)
            results[name] = {'exit': run.returncode, 'stderr': run.stderr.decode(),
                             'result': json.loads(run.stdout) if run.returncode == 0 else None}
        assert results['original']['exit'] == results['current']['exit'] == 0
        assert results['original']['result'] == results['current']['result']
        if args.include_unsafe:
            assert results['unsafe_before_fix']['exit'] == 1
            assert '64000000' in results['unsafe_before_fix']['stderr']
        print(json.dumps({name: {'exit': entry['exit'], 'stderr': entry['stderr'],
                                'cycles': entry['result']['cycles'] if entry['result'] else None}
                          for name, entry in results.items()}, indent=2))


if __name__ == '__main__':
    main()
