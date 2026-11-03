#!/usr/bin/env python3
"""Toggle only stored-order elimination; retain all prior32 regression cases."""
import argparse
import copy
import json
from pathlib import Path
import tempfile

from benchmark import join_changes, result_rows, run
from benchmark_dce import positive_cases
from compare_join_policies import ROOT, corpus


def sorted_cases():
    data = {'t': {'columns': [{'name': 'a', 'type': 'INT'}, {'name': 'b', 'type': 'NUM'},
                             {'name': 'tag', 'type': 'STR'}], 'sorted': ['a', 'b'],
                  'rows': [[None, None, 'null'], [None, '1.0', 'null-a'],
                           [1, '1.0', 'first'], [1, '1.00', 'second'],
                           [1, '2.00', 'third'], [2, None, 'last']]}}
    prefix = 'LOAD a,t.a\nLOAD b,t.b\nLOAD tag,t.tag\n'
    for name, sort, output in [
        ('full_prefix', 'SORT p,a ASC NF,b ASC NF\n', 'GATHER value,tag,p\nOUT p,value\n'),
        ('leading_prefix', 'SORT p,a ASC NF\n', 'GATHER value,tag,p\nOUT p,value\n'),
        ('destination_alias', 'SORT a,a ASC NF,b ASC NF\n', 'GATHER value,tag,a\nOUT a,value\n'),
        ('dead_first_sort', 'SORT p,a ASC NF,b ASC NF\n', 'OUT tag\n'),
        ('suffix_rejected', 'SORT p,b ASC NF\n', 'GATHER value,tag,p\nOUT p,value\n')]:
        yield 'sorted-cases', name, (prefix+sort+output).encode(), data, None, None, 'matching'
    empty = copy.deepcopy(data)
    empty['t']['rows'] = []
    source = (prefix+'SORT p,a ASC NF,b ASC NF\nGATHER value,tag,p\nOUT p,value\n').encode()
    yield 'sorted-cases', 'empty_prefix', source, empty, None, None, 'matching'
    no_order = copy.deepcopy(data)
    del no_order['t']['sorted']
    yield 'sorted-cases', 'statistics_only_rejected', source, no_order, None, None, 'matching'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    cases = [*corpus(), *corpus(True), *positive_cases(), *sorted_cases()]
    assert len(cases) == 39
    report = {'policy': 'same join and DCE algorithms; only sorted-order pass toggled', 'measurements': []}
    with tempfile.TemporaryDirectory(prefix='minivm-sorted-benchmark-') as directory:
        directory = Path(directory)
        program, schema_file, data = directory/'program.mini', directory/'schema.json', directory/'data.json'
        estimate, candidate = directory/'estimate.json', directory/'candidate.mini'
        for suite, name, source, actual, schema, estimated, status in cases:
            program.write_bytes(source)
            data.write_text(json.dumps(actual))
            if schema is None:
                estimate.write_text(json.dumps(estimated if isinstance(estimated, dict) else actual))
                encoded, _ = run([str(ROOT/'bin/minivm'), '--schema', str(estimate)])
                schema = json.loads(encoded)
                if estimated == 'omit_stats':
                    schema = {t: {k: v for k, v in table.items() if k != 'stats'} for t, table in schema.items()}
            schema_file.write_text(json.dumps(schema))
            encoded, _ = run([str(ROOT/'bin/minivm'), str(program), str(data)])
            original = json.loads(encoded)
            row = {'suite': suite, 'name': name, 'estimates': status, 'original_cycles': original['cycles']}
            outputs = {}
            for mode in ('without_sorted', 'full'):
                command = [str(ROOT/'optimize'), *(['--no-sorted-order'] if mode == 'without_sorted' else []), str(program), str(schema_file)]
                emitted, seconds = run(command)
                outputs[mode] = emitted
                events = join_changes(source, emitted, allow_dead=True, allow_sorted=mode == 'full')
                candidate.write_bytes(emitted)
                encoded, vm_seconds = run([str(ROOT/'bin/minivm'), str(candidate), str(data)])
                result = json.loads(encoded)
                if result_rows(result) != result_rows(original):
                    raise ValueError(name+': changed exact result under '+mode)
                row[mode] = {'cycles': result['cycles'], 'optimizer_seconds': seconds,
                             'vm_seconds': vm_seconds, 'changes': events, 'exact_result_equal': True}
            changes = join_changes(outputs['without_sorted'], outputs['full'], allow_dead=True, allow_sorted=True)
            if any(c['from'].upper() in ('NLJOIN', 'HJOIN') for c in changes):
                raise ValueError(name+': join choice changed during sorted-order comparison')
            row['incremental_changes'] = changes
            row['cycles_saved'] = row['without_sorted']['cycles'] - row['full']['cycles']
            report['measurements'].append(row)
            print(name, row['without_sorted']['cycles'], '->', row['full']['cycles'], 'saved', row['cycles_saved'], flush=True)
    report['totals'] = {suite: {mode: sum(r[mode]['cycles'] for r in report['measurements'] if r['suite'] == suite)
                               for mode in ('without_sorted', 'full')}
                        for suite in sorted({r['suite'] for r in report['measurements']})}
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
