"""Independent executable contract for the join-algorithm-only milestone."""

import json
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
VM = ROOT / 'bin/minivm'


def table(kind, values):
    return {'columns': [{'name': 'k', 'type': kind}], 'rows': [[v] for v in values]}


def data(left, right, left_type='INT', right_type='INT'):
    return {'l': table(left_type, left), 'r': table(right_type, right)}


def program(opcode, flag='', outputs='a,b', left_dest='a', right_dest='b'):
    return f'LOAD x,l.k\nLOAD y,r.k\n{opcode} {left_dest},{right_dest},x,y{flag}\nOUT {outputs}\n'


@unittest.skipUnless(VM.is_file(), 'supplied MiniVM is local only')
class JoinSelectionReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minivm-join-review-')
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def run_vm(self, source, tables):
        source_path, data_path = self.folder / 'p.mini', self.folder / 'data.json'
        source_path.write_text(source)
        data_path.write_text(json.dumps(tables))
        got = subprocess.run([str(VM), str(source_path), str(data_path)],
                             capture_output=True, text=True, timeout=10)
        return got, json.loads(got.stdout) if got.returncode == 0 else None

    def schema(self, tables):
        path = self.folder / 'data.json'
        path.write_text(json.dumps(tables))
        got = subprocess.run([str(VM), '--schema', str(path)],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(got.returncode, 0, got.stderr)
        return json.loads(got.stdout)

    def optimize(self, source, schema):
        source_path, schema_path = self.folder / 'p.mini', self.folder / 'schema.json'
        source_path.write_bytes(source.encode())
        schema_path.write_text(json.dumps(schema))
        got = subprocess.run([str(ROOT / 'optimize'), str(source_path), str(schema_path)],
                             capture_output=True, timeout=10)
        self.assertEqual(got.returncode, 0, got.stderr)
        return got.stdout.decode()

    def assert_algorithms(self, source, tables, expected=None, error=None):
        results = []
        for opcode in ('NLJOIN', 'HJOIN'):
            proc, output = self.run_vm(source.replace('@JOIN@', opcode), tables)
            if error:
                self.assertEqual(proc.returncode, 1, proc.stdout)
                self.assertEqual(proc.stdout, '')
                self.assertIn(error, proc.stderr)
            else:
                self.assertEqual(proc.returncode, 0, proc.stderr)
                results.append((output['ncols'], output['rows']))
                if expected is not None:
                    self.assertEqual(output['rows'], expected)
        if results:
            self.assertEqual(results[0], results[1])

    def test_random_duplicate_null_pairs_against_independent_oracle(self):
        rng = random.Random(44119)
        for _ in range(20):
            left = [rng.choice([None, -1, 0, 1]) for _ in range(rng.randrange(7))]
            right = [rng.choice([None, -1, 0, 1]) for _ in range(rng.randrange(7))]
            for null_equal in (False, True):
                pairs = [[i, j] for i, x in enumerate(left) for j, y in enumerate(right)
                         if x == y and (x is not None or null_equal)]
                with self.subTest(left=left, right=right, null_equal=null_equal):
                    self.assert_algorithms(program('@JOIN@', ',NULLEQ' if null_equal else ''),
                                           data(left, right), pairs)

    def test_numeric_cross_types_exact_comparison(self):
        self.assert_algorithms(program('@JOIN@'),
                               data([1, 2, None, -2147483648], ['1.00', '2.0', '1.0000000000000000000000000001', None, '-2147483648.00'], 'INT', 'NUM'),
                               [[0, 0], [1, 1], [3, 4]])
        source = 'LOAD z,l.k\nFILL x,79228162514264337593543950336,z\nLOAD y,r.k\n@JOIN@ a,b,x,y\nOUT a,b\n'
        self.assert_algorithms(source, data([1], ['1.0'], 'INT', 'NUM'), [])

    def test_type_errors_empty_and_null_inputs(self):
        self.assert_algorithms(program('@JOIN@'), data([1], ['1'], 'INT', 'STR'), error='expected a number, got STR')
        for left, right in [([], ['s']), ([1], []), ([None], ['s']), ([1], [None])]:
            self.assert_algorithms(program('@JOIN@'), data(left, right, 'INT', 'STR'), [])
        mixed = 'LOAD x,l.k\nEQ c,x,0\nIF x,c,1,\'s\'\nLOAD y,r.k\n@JOIN@ a,b,x,y\nOUT a,b\n'
        self.assert_algorithms(mixed, data([0, 1], [1]), error='expected a number, got STR')

    def test_destination_input_aliases_and_reassignment(self):
        tables = data([2, None, 2], [None, 2, 2])
        pairs = [[0, 1], [0, 2], [2, 1], [2, 2]]
        for ld, rd, out, expected in [('a', 'a', 'a', [[p[1]] for p in pairs]),
                                      ('x', 'y', 'x,y', pairs),
                                      ('x', 'x', 'x', [[p[1]] for p in pairs])]:
            self.assert_algorithms(program('@JOIN@', outputs=out, left_dest=ld, right_dest=rd), tables, expected)
        source = 'LOAD x,l.k\nLOAD y,r.k\n@JOIN@ x,y,x,y,NULLEQ\nLOAD x,l.k\n@JOIN@ a,b,x,x\nOUT a,b\n'
        self.assert_algorithms(source, tables, [[0, 0], [0, 2], [2, 0], [2, 2]])

    def test_small_and_large_raw_algorithm_costs(self):
        for n, nested_cycles, hash_cycles in [(2, 28, 48), (64, 4368, 1040)]:
            tables = data(list(range(n)), list(range(n)))
            _, nested = self.run_vm(program('NLJOIN'), tables)
            _, hashed = self.run_vm(program('HJOIN'), tables)
            self.assertEqual(nested['cycles'], nested_cycles)
            self.assertEqual(hashed['cycles'], hash_cycles)

    def test_optimizer_changes_only_join_opcode_bytes(self):
        tables = data(list(range(64)), list(range(64)))
        source = "; HJOIN ignored,a,x,y\r\nLOAD x,l.k\r\nLOAD y,r.k\r\nFILL text,'it''s; NLJOIN a,b,x,y',x\r\nFILL date,#2024-02-29#,x\r\n\t nLjOiN\t a , b , x , y , nUlLeQ ; café comment\r\nOUT a,b"
        chosen = self.optimize(source, self.schema(tables))
        self.assertEqual(chosen, source.replace('nLjOiN', 'HJOIN'))
        before, expected = self.run_vm(source, tables)
        after, actual = self.run_vm(chosen, tables)
        self.assertEqual((before.returncode, after.returncode), (0, 0))
        self.assertEqual(expected['rows'], actual['rows'])

    def test_unknown_estimates_leave_source_unchanged(self):
        source = program('NLJOIN')
        declarations = {'l': {'columns': [{'name': 'k', 'type': 'INT'}]},
                        'r': {'columns': [{'name': 'k', 'type': 'INT'}]}}
        self.assertEqual(self.optimize(source, declarations), source)

    def test_join_output_estimates_do_not_reuse_overwritten_load_facts(self):
        tables = data(list(range(64)), list(range(64)))
        source = 'LOAD x,l.k\nLOAD y,r.k\nNLJOIN x,y,x,y,NULLEQ\nNLJOIN a,b,x,y\nOUT a,b\n'
        schema = self.schema(tables)
        for item in schema.values():
            item['stats']['columns']['k'].pop('distinct', None)
        chosen = self.optimize(source, schema)
        self.assertEqual(chosen, source.replace('NLJOIN', 'HJOIN', 1))
        _, expected = self.run_vm(source, tables)
        _, actual = self.run_vm(chosen, tables)
        self.assertEqual(expected['rows'], actual['rows'])

    def test_non_lf_separator_inside_literal_is_not_an_instruction(self):
        tables = data(list(range(64)), list(range(64)))
        schema = self.schema(tables)
        for separator in ['\r', '\v', '\f', '\x1c', '\x1d', '\x1e', '\u0085', '\u2028', '\u2029']:
            with self.subTest(separator=repr(separator)):
                source = ("LOAD z,l.k\nFILL text,'prefix" + separator + 'LOAD x,l.k' +
                          separator + 'LOAD y,r.k' + separator + 'NLJOIN a,b,x,y' +
                          separator + "suffix',z\nOUT text\n")
                candidate = self.optimize(source, schema)
                before, expected = self.run_vm(source, tables)
                after, actual = self.run_vm(candidate, tables)
                self.assertEqual((before.returncode, after.returncode), (0, 0))
                self.assertEqual(expected['rows'], actual['rows'])
                self.assertEqual(candidate, source)

    def test_register_reassignment_uses_latest_load_estimate(self):
        tables = data(list(range(64)), list(range(64)))
        tables['small'] = table('INT', [0, 1])
        source = 'LOAD x,l.k\nLOAD y,r.k\nLOAD x,small.k\nLOAD y,small.k\nHJOIN a,b,x,y\nOUT a,b\n'
        chosen = self.optimize(source, self.schema(tables))
        self.assertEqual(chosen, source.replace('HJOIN', 'NLJOIN'))
        _, expected = self.run_vm(source, tables)
        _, actual = self.run_vm(chosen, tables)
        self.assertEqual(expected['rows'], actual['rows'])

    def test_optimizer_selects_cheaper_algorithm_on_matching_stats(self):
        for n, initial, chosen in [(2, 'HJOIN', 'NLJOIN'), (64, 'NLJOIN', 'HJOIN')]:
            tables = data(list(range(n)), list(range(n)))
            source = program(initial)
            candidate = self.optimize(source, self.schema(tables))
            self.assertEqual(candidate, source.replace(initial, chosen))
            _, before = self.run_vm(source, tables)
            _, after = self.run_vm(candidate, tables)
            self.assertEqual(before['rows'], after['rows'])
            self.assertLess(after['cycles'], before['cycles'])

    def test_stale_stats_can_regress_cost_without_changing_results(self):
        for estimate_n, actual_n, initial, expected_before, expected_after in [
                (64, 2, 'NLJOIN', 28, 48), (2, 64, 'HJOIN', 1040, 4368)]:
            estimated = data(list(range(estimate_n)), list(range(estimate_n)))
            actual = data(list(range(actual_n)), list(range(actual_n)))
            source = program(initial)
            candidate = self.optimize(source, self.schema(estimated))
            _, before = self.run_vm(source, actual)
            _, after = self.run_vm(candidate, actual)
            self.assertEqual(before['rows'], after['rows'])
            self.assertEqual((before['cycles'], after['cycles']), (expected_before, expected_after))


if __name__ == '__main__':
    unittest.main()
