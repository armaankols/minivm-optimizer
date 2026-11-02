#!/usr/bin/env python3
"""Fixed join workloads, raw NL/H comparisons, and explicit estimate failures."""
import argparse
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def data(left, right, kind='INT'):
    return {name: {'columns': [{'name': 'k', 'type': kind}],
                   'rows': [[value] for value in values]}
            for name, values in [('l', left), ('r', right)]}


def workloads():
    numeric = lambda n: data(list(range(n)), list(range(n)))
    yield 'numeric_tiny', 'HJOIN', data([0, 1], [0, 1, 2]), None, False
    yield 'numeric_large', 'NLJOIN', numeric(64), None, False
    yield 'numeric_tie', 'HJOIN', numeric(12), None, False
    yield 'empty_left', 'HJOIN', data([], list(range(32))), None, False
    yield 'duplicates_null_equal', 'HJOIN', data([None, None, 1, 1, 2], [None, 1, 1, 2]), None, True
    yield 'string_asymmetric', 'HJOIN', data(['x' * 1024] * 32, ['x'] * 32, 'STR'), None, False
    strings = ['x' * 80 + str(i) for i in range(64)]
    yield 'string_large', 'NLJOIN', data(strings, strings, 'STR'), None, False
    # min(mean bytes) overestimates mean(min(bytes)) for this skewed family.
    # Retain the cost-model regression even though statistics match actual data.
    skew = [''] * 63 + ['x' * 10_000]
    yield 'string_skew_matching_stats', 'NLJOIN', data(skew, skew, 'STR'), None, False
    yield 'stale_large_estimate_tiny_actual', 'NLJOIN', numeric(2), numeric(64), False
    yield 'stale_tiny_estimate_large_actual', 'HJOIN', numeric(64), numeric(2), False
    yield 'unknown_stats_large', 'NLJOIN', numeric(64), 'omit_stats', False


def run(command):
    start = time.monotonic()
    result = subprocess.run([str(x) for x in command], capture_output=True, check=True, timeout=60)
    return result.stdout, time.monotonic() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('optimizer', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    optimizer = args.optimizer.resolve(strict=True)
    measurements = []
    with tempfile.TemporaryDirectory(prefix='minivm-join-benchmark-') as directory:
        directory = Path(directory)
        program, candidate = directory/'original.mini', directory/'candidate.mini'
        actual_file, stats_file, schema_file = directory/'data.json', directory/'stats-data.json', directory/'schema.json'
        for name, initial, actual_data, estimated_data, null_equal in workloads():
            source = 'LOAD x,l.k\nLOAD y,r.k\n' + initial + ' a,b,x,y' + (',NULLEQ' if null_equal else '') + '\nOUT a,b\n'
            actual_file.write_text(json.dumps(actual_data))
            stats_file.write_text(json.dumps(estimated_data if isinstance(estimated_data, dict) else actual_data))
            schema_bytes, _ = run([ROOT/'bin/minivm', '--schema', stats_file])
            schema = json.loads(schema_bytes)
            if estimated_data == 'omit_stats':
                schema = {n: {k: v for k, v in table.items() if k != 'stats'} for n, table in schema.items()}
            schema_file.write_text(json.dumps(schema))
            program.write_text(source)
            candidate_bytes, optimizer_seconds = run([optimizer, program, schema_file])
            candidate.write_bytes(candidate_bytes)
            original_bytes, original_seconds = run([ROOT/'bin/minivm', program, actual_file])
            selected_bytes, selected_seconds = run([ROOT/'bin/minivm', candidate, actual_file])
            before, after = json.loads(original_bytes), json.loads(selected_bytes)
            raw = {}
            for op in ('NLJOIN', 'HJOIN'):
                program.write_text(source.replace(initial, op))
                encoded, _ = run([ROOT/'bin/minivm', program, actual_file])
                result = json.loads(encoded)
                assert result['ncols'] == before['ncols'] and result['rows'] == before['rows'], name
                raw[op] = result['cycles']
            assert before['ncols'] == after['ncols'] and before['rows'] == after['rows'], name
            choice = candidate_bytes.decode().split('\n')[2].split()[0]
            assert candidate_bytes.decode() == source.replace(initial, choice), name
            measurements.append(dict(name=name, initial=initial, selected=choice,
                baseline_cycles=before['cycles'], candidate_cycles=after['cycles'],
                cycles_saved=before['cycles']-after['cycles'], raw_algorithm_cycles=raw,
                optimizer_seconds=optimizer_seconds, original_vm_seconds=original_seconds,
                candidate_vm_seconds=selected_seconds,
                estimates='missing' if estimated_data == 'omit_stats' else 'stale' if estimated_data else 'matching'))
    report = dict(suite='join-workloads-v1', python=platform.python_version(), platform=platform.platform(),
                  policy='single invocation timings include startup; deterministic datasets; both raw algorithms executed',
                  measurements=measurements)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    for row in measurements:
        print(f"{row['name']}: {row['initial']}->{row['selected']} {row['baseline_cycles']}->{row['candidate_cycles']} (saved {row['cycles_saved']})")


if __name__ == '__main__':
    main()
