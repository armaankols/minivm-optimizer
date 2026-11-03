#!/usr/bin/env python3
"""Isolate DCE after frozen join selection; retain all29 join regression cases."""
import argparse
import json
from pathlib import Path
import tempfile

from benchmark import join_changes, result_rows, run
from compare_join_policies import ROOT, corpus


def positive_cases():
    tables = {'t': {'columns': [{'name': 'id', 'type': 'INT'}, {'name': 's', 'type': 'STR'},
                                {'name': 'd', 'type': 'DATE'}],
                    'rows': [[1, ' straße ', '2024-02-29'], [1, None, None],
                             [2, '猫', '9999-12-31'], [3, '', '0001-01-01']]}}
    for name, body in [
        ('dead_string_chain', 'LOAD s,t.s\nUPPER a,s\nTRIM b,a\nLEN c,b\n'),
        ('dead_index_chain', 'IOTA a,x\nSLICE b,a,999999999999999999999999999\nISNULL c,b\n'),
        ('dead_date_parts', 'LOAD d,t.d\nYEAR a,d\nMONTH b,d\nDAY c,d\nDOW e,d\n')]:
        yield 'positive', name, ('LOAD x,t.id\n'+body+'OUT x,x\n').encode(), tables, None, None, 'matching'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = {'policy': 'same active join choices; sorted-order pass disabled to isolate DCE', 'measurements': []}
    cases = [*corpus(), *corpus(True), *positive_cases()]
    assert len(cases) == 32
    with tempfile.TemporaryDirectory(prefix='minivm-dce-benchmark-') as directory:
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
            outputs = {}
            row = {'suite': suite, 'name': name, 'estimates': status, 'original_cycles': original['cycles']}
            for mode in ('joins_only', 'full'):
                command = [str(ROOT/'optimize'), '--joins-only' if mode == 'joins_only' else '--no-sorted-order', str(program), str(schema_file)]
                emitted, seconds = run(command)
                outputs[mode] = emitted
                changes = join_changes(source, emitted, allow_dead=mode == 'full')
                candidate.write_bytes(emitted)
                encoded, vm_seconds = run([str(ROOT/'bin/minivm'), str(candidate), str(data)])
                result = json.loads(encoded)
                if result_rows(original) != result_rows(result):
                    raise ValueError(name+': result mismatch '+mode)
                row[mode] = {'cycles': result['cycles'], 'optimizer_seconds': seconds,
                             'vm_seconds': vm_seconds, 'changes': changes, 'exact_result_equal': True}
            incremental = join_changes(outputs['joins_only'], outputs['full'], allow_dead=True)
            if any(c['to'] is not None for c in incremental):
                raise ValueError(name+': DCE contribution includes another join choice')
            row['removed'] = incremental
            row['dce_cycles_saved'] = row['joins_only']['cycles'] - row['full']['cycles']
            report['measurements'].append(row)
            print(name, row['joins_only']['cycles'], '->', row['full']['cycles'], 'DCE saved', row['dce_cycles_saved'], flush=True)
    report['totals'] = {suite: {mode: sum(r[mode]['cycles'] for r in report['measurements'] if r['suite'] == suite)
                               for mode in ('joins_only', 'full')}
                        for suite in sorted({r['suite'] for r in report['measurements']})}
    args.output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
