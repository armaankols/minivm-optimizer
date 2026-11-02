#!/usr/bin/env python3
"""Optimizer-only scale probe; not a claim of worst-case VM equivalence."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    text = 'LOAD x,l.k\nLOAD y,r.k\n' + 'NLJOIN a,b,x,y\n' * 19997 + 'OUT a,b\n'
    columns = [{'name': 'k' if i == 0 else 'c'+str(i), 'type': 'INT'} for i in range(10000)]
    table = {'columns': columns, 'stats': {'rows': 64, 'columns': {
        c['name']: {'distinct': 64, 'nulls': 0} for c in columns}}}
    with tempfile.TemporaryDirectory(prefix='minivm-join-scale-') as directory:
        directory = Path(directory)
        source, schema = directory/'scale.mini', directory/'schema.json'
        source.write_text(text)
        schema.write_text(json.dumps({'l': table, 'r': table}))
        start = time.monotonic()
        result = subprocess.run([str(ROOT/'optimize'), str(source), str(schema)],
                                capture_output=True, timeout=60)
        elapsed = time.monotonic() - start
        if result.returncode or result.stdout.decode() != text.replace('NLJOIN', 'HJOIN'):
            raise ValueError('unexpected scale-probe result')
        report = dict(purpose=__doc__, instructions=20000, schema_columns=20000,
                      program_bytes=len(text.encode()), schema_bytes=schema.stat().st_size,
                      wall_seconds=elapsed, exit=result.returncode, all_19997_join_choices_expected=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
