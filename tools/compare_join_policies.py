#!/usr/bin/env python3
"""Compare fixed example/workload corpus under original, old, new, all-H/all-NL.

The reference optimizer is recovered as text from Git, then invoked through its
command interface. No optimizer implementation is imported. Every emitted program
is audited for opcode-only changes and executed against the same frozen schema
and actual data. The corpus is unchanged from the preceding milestone.
"""
import argparse
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

from benchmark import join_changes, result_rows
from benchmark_joins import data, workloads

ROOT = Path(__file__).resolve().parents[1]
FORCE_SCRIPT = '''#!{python}
import pathlib,re,sys
policy={policy!r}
source=pathlib.Path(sys.argv[1]).read_bytes()
lines=source.split(b'\\n')
for i,line in enumerate(lines):
    match=re.match(rb'[ \\t]*(NLJOIN|HJOIN)(?=[ \\t])',line,re.IGNORECASE)
    if match and match.group(1).upper()!=policy:
        lines[i]=line[:match.start(1)]+policy+line[match.end(1):]
sys.stdout.buffer.write(b'\\n'.join(lines))
'''


def run(command):
    started = time.monotonic()
    result = subprocess.run([str(x) for x in command], capture_output=True, check=True, timeout=60)
    return result.stdout, time.monotonic() - started


def profile_holdouts():
    nulls = [None] * 63 + ['x' * 10000]
    for flag in (False, True):
        yield 'null_skew_'+str(flag).lower(), data(nulls, nulls, 'STR'), flag, 'HJOIN'
    emoji = [''] * 63 + ['🙂' * 1000]
    yield 'utf8_4000_byte_tail', data(emoji, emoji, 'STR'), False, 'HJOIN'
    ascii_tail = [''] * 63 + ['x' * 1000]
    yield 'ascii_1000_byte_tail', data(ascii_tail, ascii_tail, 'STR'), False, 'NLJOIN'
    full = [''] * 5 + ['猫' * 4] * 3
    yield 'full_common_utf8', data(full, full, 'STR'), False, 'NLJOIN'
    homogeneous = [''] * 60 + [str(i) * 2500 for i in range(1, 5)]
    yield 'homogeneous_residual', data(homogeneous, homogeneous, 'STR'), False, 'NLJOIN'
    truncated = [c for c in 'ABCDEFGH' for _ in range(4)] + [chr(i) for i in range(33, 64)] + ['x' * 10000]
    yield 'truncated_common_heterogeneous_tail', data(truncated, truncated, 'STR'), False, 'NLJOIN'
    right = [f'{i:04d}' for i in range(977)] + [f'z{i:04d}' for i in range(23)]
    yield 'rounded_average_near_tie', data(['zzzzz'] * 2, right, 'STR'), False, 'HJOIN'
    near_zero = ['x'] * 198 + ['']
    yield 'rounded_negative_central_residual', data(near_zero, near_zero, 'STR'), False, 'NLJOIN'


def corpus(holdouts_only=False):
    if holdouts_only:
        for name, actual, null_equal, initial in profile_holdouts():
            source = ('LOAD x,l.k\nLOAD y,r.k\n'+initial+' a,b,x,y'+
                      (',NULLEQ' if null_equal else '')+'\nOUT a,b\n').encode()
            yield 'holdouts', name, source, actual, None, None, 'matching'
        skew = [''] * 63 + ['x' * 10000]
        source = b'LOAD x,l.k\nLOAD y,r.k\nHJOIN a,b,x,y\nOUT a,b\n'
        yield 'holdouts', 'stale_profile_distribution', source, data(['x']*64, ['x']*64, 'STR'), None, data(skew, skew, 'STR'), 'stale'
        return
    actual = json.loads((ROOT/'examples/data.json').read_text())
    schema = json.loads((ROOT/'examples/schema.json').read_text())
    for program in sorted((ROOT/'examples/programs').glob('*.mini')):
        yield 'examples', program.stem, program.read_bytes(), actual, schema, None, 'supplied'
    for name, initial, actual, estimated, null_equal in workloads():
        source = ('LOAD x,l.k\nLOAD y,r.k\n'+initial+' a,b,x,y'+
                  (',NULLEQ' if null_equal else '')+'\nOUT a,b\n').encode()
        yield 'targeted', name, source, actual, None, estimated, (
            'missing' if estimated == 'omit_stats' else 'stale' if estimated else 'matching')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--optimizer', type=Path, default=ROOT/'optimize')
    parser.add_argument('--reference-commit', default='3155414')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--holdouts-only', action='store_true', help='separate profile holdouts; does not alter the fixed 19-case corpus')
    args = parser.parse_args()
    ref = subprocess.check_output(['git', 'rev-parse', '--verify', args.reference_commit+'^{commit}'], cwd=ROOT, text=True).strip()
    reference_source = subprocess.check_output(['git', 'show', ref+':optimizer.py'], cwd=ROOT)
    report = dict(reference_commit=ref, corpus='profile-holdouts-v1' if args.holdouts_only else 'supplied-examples-v1 + join-workloads-v1',
                  platform=platform.platform(), measurements=[])
    with tempfile.TemporaryDirectory(prefix='minivm-policy-comparison-') as directory:
        directory = Path(directory)
        previous = directory/'previous_optimizer'
        previous.write_bytes(reference_source)
        previous.chmod(0o755)
        policies = {'previous': previous, 'current': args.optimizer.resolve()}
        for name, opcode in [('always_HJOIN', b'HJOIN'), ('always_NLJOIN', b'NLJOIN')]:
            script = directory/name
            script.write_text(FORCE_SCRIPT.format(python=sys.executable, policy=opcode))
            script.chmod(0o755)
            policies[name] = script
        program, data, schema_file = directory/'original.mini', directory/'data.json', directory/'schema.json'
        candidate, estimate_file = directory/'candidate.mini', directory/'estimate-data.json'
        for suite, name, source, actual, schema, estimated, status in corpus(args.holdouts_only):
            program.write_bytes(source)
            data.write_text(json.dumps(actual))
            if schema is None:
                estimate_file.write_text(json.dumps(estimated if isinstance(estimated, dict) else actual))
                encoded, _ = run([ROOT/'bin/minivm', '--schema', estimate_file])
                schema = json.loads(encoded)
                if estimated == 'omit_stats':
                    schema = {t: {k: v for k, v in table.items() if k != 'stats'} for t, table in schema.items()}
            schema_file.write_text(json.dumps(schema))
            encoded, seconds = run([ROOT/'bin/minivm', program, data])
            original = json.loads(encoded)
            row = dict(suite=suite, name=name, estimates=status, original_cycles=original['cycles'],
                       policies={'original': dict(cycles=original['cycles'], vm_seconds=seconds)})
            for policy, executable in policies.items():
                optimized, optimizer_seconds = run([executable, program, schema_file])
                changes = join_changes(source, optimized)
                candidate.write_bytes(optimized)
                encoded, vm_seconds = run([ROOT/'bin/minivm', candidate, data])
                result = json.loads(encoded)
                if result_rows(original) != result_rows(result):
                    raise ValueError(f'result mismatch: {name} {policy}')
                row['policies'][policy] = dict(cycles=result['cycles'], optimizer_seconds=optimizer_seconds,
                    vm_seconds=vm_seconds, changes=changes, exact_result_equal=True)
            report['measurements'].append(row)
            print(name, {p: values['cycles'] for p, values in row['policies'].items()}, flush=True)
        report['totals'] = {suite: {p: sum(r['policies'][p]['cycles'] for r in report['measurements'] if r['suite'] == suite)
                                     for p in ('original', *policies)} for suite in sorted({r['suite'] for r in report['measurements']})}
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
