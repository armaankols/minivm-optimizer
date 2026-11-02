"""Independent black-box optimizer and comparator challenges.

These cases are deliberately separate from evaluator-owned fixtures. They use the
required external optimizer command interface and MiniVM as the result oracle.
"""

import itertools
import json
from pathlib import Path
import random
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evaluator  # noqa: E402


def result(rows, ncols=1):
    return evaluator.parse_result(json.dumps(dict(ncols=ncols, rows=rows, cycles=4)).encode())


class ComparatorChallenges(unittest.TestCase):
    def compare(self, expected, actual, kinds, ordered=False):
        return evaluator.compare_results(result(expected, len(kinds)),
                                         result(actual, len(kinds)), kinds, ordered)[0]

    def test_type_multiplicity_associations_and_order(self):
        self.assertFalse(self.compare([[1]], [[True]], ('INT',)))
        self.assertFalse(self.compare([[True]], [[1]], ('BOOL',)))
        self.assertFalse(self.compare([[1], [1], [2]], [[1], [2], [2]], ('INT',)))
        self.assertFalse(self.compare([[1, 'a'], [2, 'b']], [[1, 'b'], [2, 'a']], ('INT', 'STR')))
        self.assertTrue(self.compare([[1, 'a'], [2, 'b']], [[2, 'b'], [1, 'a']], ('INT', 'STR')))
        self.assertFalse(self.compare([[1], [2]], [[2], [1]], ('INT',), ordered=True))

    def test_numeric_type_metadata_and_zero(self):
        self.assertFalse(self.compare([['1.0']], [['1.0000001']], ('STR',)))
        self.assertTrue(self.compare([['1.0']], [['1.0000001']], ('NUM',)))
        self.assertFalse(self.compare([['0']], [['0.0000000000000000000000000001']], ('NUM',)))
        self.assertTrue(self.compare([['170141183460469231731687303715884105727']],
                                     [['170141183460469231731687303715884105726']], ('INT',)))

    def test_non_vm_numeric_strings_are_not_numeric_output(self):
        for bad in ['1e1000000', ' 1.0 ', '1_0e-1', 'NaN', 'Infinity']:
            with self.subTest(value=bad):
                self.assertFalse(self.compare([['1.0']], [[bad]], ('NUM',)))

    def test_numeric_contract_allows_int_num_type_and_scale_changes(self):
        self.assertTrue(self.compare([[1], [2], [None]], [['1.0'], ['2.00'], [None]], ('INT',)))
        self.assertTrue(self.compare([[1]], [['1.0000001']], ('INT',)))
        self.assertFalse(self.compare([[1]], [['1.1']], ('INT',)))
        self.assertTrue(self.compare([[0]], [['0.000']], ('INT',)))
        self.assertFalse(self.compare([[1]], [[True]], ('INT',)))
        self.assertFalse(self.compare([['1.0']], [['1.00']], ('STR',)))

    def test_non_greedy_matching_against_small_exhaustive_oracle(self):
        # First expected row can match either actual row; second has only one.
        self.assertTrue(self.compare([['1.0000000'], ['1.0000018']],
                                     [['1.0000009'], ['0.9999992']], ('NUM',)))
        rng = random.Random(65843)
        pool = ['0.9999992', '1.0000000', '1.0000009', '1.0000018', '2.0', None]
        for _ in range(100):
            n = rng.randrange(6)
            left, right = [[rng.choice(pool)] for _ in range(n)], [[rng.choice(pool)] for _ in range(n)]
            brute = any(all(evaluator.cell_equal(a[0], b[0], 'NUM')
                            for a, b in zip(left, candidate))
                        for candidate in itertools.permutations(right))
            self.assertEqual(self.compare(left, right, ('NUM',)), brute, (left, right))

    def test_malformed_vm_output(self):
        for raw in [b'{"ncols":1,"ncols":1,"rows":[],"cycles":0}',
                    b'{"ncols":true,"rows":[],"cycles":0}',
                    b'{"ncols":1,"rows":[[1,2]],"cycles":0}',
                    b'{"ncols":1,"rows":[[1.5]],"cycles":0}',
                    b'{"ncols":1,"rows":[[NaN]],"cycles":0}',
                    b'{"ncols":1,"rows":[],"cycles":0} trailing']:
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                evaluator.parse_result(raw)


@unittest.skipUnless((ROOT / 'bin/minivm').is_file(), 'supplied interpreter is local only')
class ExternalOptimizerChallenges(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minivm-review-contract-')
        self.directory = Path(self.temp.name)
        columns = [dict(name='x', type='INT')]
        self.case = evaluator.Case('review-frozen-stats', 'LOAD x,t.x\nOUT x\n',
                                  ('INT',), False,
                                  [{'t': dict(columns=columns, rows=[[7], [7]])},
                                   {'t': dict(columns=columns, rows=[[7], [7], [8]])}])

    def tearDown(self):
        self.temp.cleanup()

    def optimizer(self, source):
        path = self.directory / 'optimizer with spaces'
        path.write_text('#!/usr/bin/env python3\n' + source)
        path.chmod(0o755)
        return path

    def evaluate(self, optimizer, **kwargs):
        return evaluator.evaluate(optimizer, cases=[self.case],
                                  artifact_root=self.directory / 'failures', **kwargs)

    def test_identity_accepts_alternatives_with_one_frozen_schema(self):
        optimizer = self.optimizer('import pathlib,sys\nprint(pathlib.Path(sys.argv[1]).read_text())\n')
        summary = self.evaluate(optimizer)
        self.assertEqual(summary['executions'], 2)

    def test_stats_based_slice_is_rejected_and_witness_retained(self):
        optimizer = self.optimizer("import json,sys\nn=json.load(open(sys.argv[2]))['t']['stats']['rows']\nprint(f'LOAD x,t.x\\nSLICE y,x,{n}\\nOUT y')\n")
        with self.assertRaises(evaluator.Defect):
            self.evaluate(optimizer)
        failures = list((self.directory / 'failures').glob('*/failure.json'))
        self.assertEqual(len(failures), 1)
        folder = failures[0].parent
        self.assertEqual(len(json.loads((folder / 'data.json').read_text())['t']['rows']), 3)
        self.assertEqual(json.loads((folder / 'schema.json').read_text())['t']['stats']['rows'], 2)

    def test_unsorted_filter_may_reorder_whole_rows(self):
        # Regression for an overly strict ordered flag found during review.
        self.case = next(case for case in evaluator.make_cases() if case.name == 'filter')
        optimizer = self.optimizer("import pathlib,sys\np=pathlib.Path(sys.argv[1]).read_text()\np=p.rsplit('OUT a,b',1)[0]\nprint(p+'SORT review_order,a DESC NL\\nGATHER review_a,a,review_order\\nGATHER review_b,b,review_order\\nOUT review_a,review_b')\n")
        self.assertEqual(self.evaluate(optimizer)['executions'], len(self.case.datasets))

    def test_changed_alternative_constraints_are_incomplete(self):
        self.case.datasets[1]['t']['not_null'] = ['x']
        optimizer = self.optimizer('import pathlib,sys\nprint(pathlib.Path(sys.argv[1]).read_text())\n')
        with self.assertRaises(evaluator.EvaluationError):
            self.evaluate(optimizer)

    def test_huge_exponent_string_is_defect_with_witness(self):
        optimizer = self.optimizer("print(\"LOAD x,t.x\\nFILL bad,'1e1000000',x\\nOUT bad\")\n")
        with self.assertRaises(evaluator.Defect):
            self.evaluate(optimizer)
        self.assertEqual(len(list((self.directory / 'failures').glob('*/failure.json'))), 1)

    def test_exact_int_to_num_rewrite_is_accepted_on_boundaries(self):
        rng = random.Random(19741)
        rows = [[-2147483648], [2147483647], [0], [1], [2], [None]]
        rows += [[rng.randrange(-2147483648, 2147483648)] for _ in range(10)]
        self.case.datasets = [
            {'t': dict(columns=[dict(name='x', type='INT')], rows=rows)},
            {'t': dict(columns=[dict(name='x', type='INT')], rows=[])},
        ]
        optimizer = self.optimizer("print('LOAD x,t.x\\nADD y,x,0.1\\nSUB y,y,0.1\\nOUT y')\n")
        self.assertEqual(self.evaluate(optimizer)['executions'], 2)

    def test_empty_program_nonzero_exit_and_invalid_utf8(self):
        for source in ['pass\n', 'raise SystemExit(7)\n',
                       "import sys\nsys.stdout.buffer.write(b'\\xff')\n"]:
            with self.subTest(source=source), self.assertRaises(evaluator.Defect):
                self.evaluate(self.optimizer(source))

    def test_global_deadline_is_incomplete_not_clean_or_optimizer_defect(self):
        optimizer = self.optimizer('import time\ntime.sleep(10)\n')
        started = time.monotonic()
        with self.assertRaises(evaluator.EvaluationError):
            self.evaluate(optimizer, budget=0.15, optimizer_timeout=60)
        self.assertLess(time.monotonic() - started, 2)


class ProcessChallenges(unittest.TestCase):
    def test_child_holding_pipe_is_killed_on_timeout(self):
        command = [sys.executable, '-c',
                   'import os,time; p=os.fork(); time.sleep(10) if p==0 else None']
        started = time.monotonic()
        got = evaluator.run_process(command, 0.15, started + 3)
        self.assertEqual(got.issue, 'subprocess timed out')
        self.assertLess(time.monotonic() - started, 2)

    def test_stdout_limit(self):
        got = evaluator.run_process([sys.executable, '-c', 'print("x"*10000)'],
                                    2, time.monotonic() + 3, stdout_limit=20)
        self.assertEqual(got.issue, 'stdout exceeded byte limit')
        self.assertEqual(len(got.stdout), 20)


if __name__ == '__main__':
    unittest.main()
