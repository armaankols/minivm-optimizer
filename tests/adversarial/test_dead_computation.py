"""Independent black-box tests for the explicitly narrow DCE whitelist."""

import json
import subprocess
import unittest

import test_join_selection as joins


def tables(empty=False):
    return {
        't': {'columns': [{'name': 'x', 'type': 'INT'}, {'name': 's', 'type': 'STR'},
                          {'name': 'd', 'type': 'DATE'}, {'name': 'n', 'type': 'NUM'}],
              'rows': [] if empty else [[3, ' straße ', '2024-02-29', '1.25'],
                                        [3, 'x', '0001-01-01', '0.0'],
                                        [None, None, None, None],
                                        [1, '', '9999-12-31', '2.50']]},
        'u': {'columns': [{'name': 's', 'type': 'STR'}, {'name': 'x', 'type': 'INT'}],
              'rows': [] if empty else [['a', 1], ['b', 2], ['c', 3]]},
    }


def ops(source):
    # Only used on fixtures without semicolons inside literals.
    return [line.split(';', 1)[0].strip().split()[0].upper()
            for line in source.split('\n') if line.split(';', 1)[0].strip()]


class DeadComputationReview(unittest.TestCase):
    setUp = joins.JoinSelectionReview.setUp
    tearDown = joins.JoinSelectionReview.tearDown
    run_vm = joins.JoinSelectionReview.run_vm
    schema = joins.JoinSelectionReview.schema

    def optimize(self, source, schema):
        path, schema_path = self.folder / 'original.mini', self.folder / 'schema.json'
        path.write_bytes(source.encode())
        schema_path.write_text(json.dumps(schema))
        proc = subprocess.run([str(joins.ROOT / 'optimize'), str(path), str(schema_path)],
                              capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode()

    def compare(self, source, *, estimated=None, actual=None, error=False):
        actual = tables() if actual is None else actual
        candidate = self.optimize(source, self.schema(actual if estimated is None else estimated))
        old, expected = self.run_vm(source, actual)
        new, selected = self.run_vm(candidate, actual)
        if error:
            self.assertEqual(old.returncode, 1, old.stdout)
            self.assertEqual(new.returncode, 1, new.stdout)
            self.assertEqual(new.stdout, '')
        else:
            self.assertEqual((old.returncode, new.returncode), (0, 0), (old.stderr, new.stderr))
            self.assertEqual(expected['ncols'], selected['ncols'])
            self.assertEqual(expected['rows'], selected['rows'])
        self.assertEqual(source.count('\n'), candidate.count('\n'))
        return candidate, expected, selected

    def test_dead_whitelist_chain_disappears_and_preserves_duplicate_columns(self):
        source = ('LOAD x,t.x\nLOAD s,t.s\nUPPER a,s\nRTRIM b,a\nTRIM c,b\n'
                  'LEN n,c\nNULLIFE e,c\nLEFT l,e,3\nSUBSTR z,l,1,3\n'
                  'ISNULL m,n\nIOTA i,m\nSLICE q,i,999999999999999999999999999999999999999999\n'
                  'LOAD d,t.d\nYEAR y,d\nMONTH mo,d\nDAY daypart,d\nDOW dw,d\nOUT x,x\n')
        candidate, before, after = self.compare(source)
        self.assertEqual(ops(candidate), ['LOAD', 'OUT'])
        self.assertLess(after['cycles'], before['cycles'])

    def test_reassignment_and_read_write_aliases_use_correct_definitions(self):
        source = 'LOAD x,t.s\nLEN x,x\nIOTA x,x\nLOAD x,t.x\nOUT x\n'
        candidate, _, _ = self.compare(source)
        # Every overwrite may release an old value, including a long STR before
        # LEN/IOTA and the final LOAD. Preserve explicit lifetime boundaries.
        self.assertEqual(ops(candidate), ['LOAD', 'LEN', 'IOTA', 'LOAD', 'OUT'])
        source = 'LOAD x,t.x\nUPPER dead,x\nLOAD x,t.s\nOUT x\n'
        candidate, _, _ = self.compare(source, error=True)
        self.assertIn('UPPER dead,x', candidate)
        self.assertIn('LOAD x,t.x', candidate)

    def test_dead_erroring_arithmetic_is_retained_with_its_inputs(self):
        for operation in ['DIV bad,x,0', 'MOD bad,x,0',
                          'MUL bad,x,170141183460469231731687303715884105727']:
            with self.subTest(operation=operation):
                source = 'LOAD x,t.x\n'+operation+'\nLOAD x,t.s\nOUT x\n'
                candidate, _, _ = self.compare(source, error=True)
                self.assertIn(operation, candidate)
                self.assertIn('LOAD x,t.x', candidate)

    def test_missing_stored_column_is_not_removable(self):
        for reference in ['t.absent', 'absent.x']:
            with self.subTest(reference=reference):
                source = f'LOAD x,t.x\nLOAD bad,{reference}\nOUT x\n'
                candidate, _, _ = self.compare(source, error=True)
                self.assertIn('LOAD bad,'+reference, candidate)

    def test_python_only_whitespace_does_not_validate_malformed_load(self):
        for separator in ['\x1c', '\x1d', '\x1e', '\x1f']:
            with self.subTest(separator=repr(separator)):
                source = 'LOAD dead,t.x'+separator+'\nLOAD x,t.x\nOUT x\n'
                self.compare(source, error=True)

    def test_unicode_casefold_is_not_a_valid_stored_identifier(self):
        actual = tables()
        actual['t']['columns'].append({'name': 'k', 'type': 'INT'})
        for row in actual['t']['rows']:
            row.append(1)
        source = 'LOAD dead,t.K\nLOAD x,t.x\nOUT x\n'
        self.compare(source, actual=actual, error=True)

    def test_group_and_undefined_sources_do_not_prove_column_totality(self):
        for operation in ['IOTA bad,g', 'SLICE bad,g,0', 'ISNULL bad,g',
                          'UPPER bad,g', 'IOTA bad,undefined', 'SLICE bad,undefined,0']:
            with self.subTest(operation=operation):
                source = 'LOAD x,t.x\nGALL g,x\n'+operation+'\nOUT x\n'
                self.compare(source, error=True)

    def test_wrong_types_and_invalid_counts_remain_errors(self):
        operations = ['UPPER bad,x', 'RTRIM bad,x', 'TRIM bad,x', 'LEN bad,x',
                      'NULLIFE bad,x', 'LEFT bad,s,-1', 'LEFT bad,s,x',
                      'SUBSTR bad,s,0,2', 'SUBSTR bad,s,1,-1',
                      'YEAR bad,s', 'MONTH bad,x', 'DAY bad,x', 'DOW bad,x',
                      "UPPER bad,'literal'", 'IOTA bad,NULL']
        for operation in operations:
            with self.subTest(operation=operation):
                self.compare('LOAD x,t.x\nLOAD s,t.s\n'+operation+'\nOUT x\n', error=True)

    def test_invalid_fill_literals_and_sources_are_not_eliminated(self):
        operations = [
            'FILL bad,170141183460469231731687303715884105728,x',
            'FILL bad,9999999999999999999999999999.9,x',
            'FILL bad,#2023-02-29#,x', 'FILL bad,#0000-01-01#,x',
            "FILL bad,'unterminated,x", "FILL bad,'x',undefined",
        ]
        for operation in operations:
            with self.subTest(operation=operation):
                self.compare('LOAD x,t.x\n'+operation+'\nOUT x\n', error=True)

    def test_index_and_length_errors_cannot_be_removed(self):
        prefixes = [
            'LOAD y,u.x\nIOTA i,y\nGATHER bad,y,i\nIOTA j,x\nGATHER bad,y,j\n',
            'FILL i,NULL,x\nGATHER bad,x,i\n',
            'LOAD y,u.s\nCAT bad,s,y\n',
        ]
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.compare('LOAD x,t.x\nLOAD s,t.s\n'+prefix+'OUT x\n', error=True)

    def test_empty_snapshot_does_not_prove_future_type_or_arithmetic_safety(self):
        for operation in ['UPPER bad,x', 'DIV bad,x,0']:
            with self.subTest(operation=operation):
                self.compare('LOAD x,t.x\n'+operation+'\nOUT x\n',
                             estimated=tables(empty=True), actual=tables(), error=True)

    def test_nonwhitelist_total_looking_instructions_still_retained(self):
        prefixes = ["FILL bad,'constant',x\n", 'ADD bad,x,1\n',
                    'LOAD n,t.n\nTRUNC bad,n\n', 'SORT bad,x ASC NF\n',
                    'IOTA i,x\nGATHER bad,x,i\n', 'GALL bad,x\n',
                    'GROUP bad,x\n', 'HJOIN a,b,x,x\n']
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                candidate, _, _ = self.compare('LOAD x,t.x\n'+prefix+'OUT x\n')
                for line in prefix.strip().split('\n'):
                    # A join algorithm may change independently; no join removal.
                    if line.startswith('HJOIN'):
                        self.assertTrue('HJOIN a,b,x,x' in candidate or 'NLJOIN a,b,x,x' in candidate)
                    else:
                        self.assertIn(line, candidate)

    def test_retained_instructions_keep_whitelist_input_definitions_live(self):
        prefixes = [
            'IOTA i,x\nSORT bad,i ASC NF\n',
            'IOTA i,x\nTOPK bad,2,i DESC NL\n',
            'IOTA i,x\nGROUP bad,i\n',
            'IOTA i,x\nFILL bad,1,i\n',
            'IOTA i,x\nHJOIN a,b,i,i,NULLEQ\n',
            'ISNULL c,x\nIOTA i,x\nIF bad,c,i,x\n',
            "LOAD s,t.s\nUPPER u,s\nCAT bad,u,'suffix'\n",
            'IOTA i,x\nGALL g,x\nGSUM bad,g,i\n',
        ]
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                candidate, _, _ = self.compare('LOAD x,t.x\n'+prefix+'OUT x\n')
                for line in prefix.strip().split('\n'):
                    if not line.startswith('HJOIN'):
                        self.assertIn(line, candidate)

    def test_join_writes_both_destinations_and_reads_aliases_before_writes(self):
        source = 'LOAD a,t.s\nLOAD b,t.d\nLOAD x,t.x\nHJOIN a,b,x,x\nOUT a\n'
        candidate, _, _ = self.compare(source)
        self.assertNotIn('LOAD a,t.s', candidate)
        self.assertNotIn('LOAD b,t.d', candidate)
        for destinations, output in [('a,b', 'b'), ('a,a', 'a')]:
            with self.subTest(destinations=destinations):
                source = f'LOAD a,t.x\nHJOIN {destinations},a,a\nOUT {output}\n'
                candidate, _, _ = self.compare(source)
                self.assertIn('LOAD a,t.x', candidate)

    def test_crlf_comments_and_live_control_separators_survive(self):
        for separator in ['\r', '\v', '\f', '\x1c', '\x1d', '\x1e', '\u0085', '\u2028', '\u2029']:
            with self.subTest(separator=repr(separator)):
                source = ("LOAD x,t.x\r\nLOAD unused,t.s ; café preserve\r\nFILL text,'it''s;"+
                          separator+'LOAD fake,t.s'+separator+"UPPER fake,fake',x\r\nOUT text")
                candidate, _, _ = self.compare(source)
                self.assertNotIn('LOAD unused,t.s', candidate)
                self.assertIn('; café preserve\r\n', candidate)
                self.assertEqual(candidate.count('\r\n'), source.count('\r\n'))
                self.assertFalse(candidate.endswith('\n'))

    def test_unknown_opcode_falls_back_without_dce(self):
        source = 'LOAD unused,t.s\nLOAD x,t.x\nMYSTERY bad,x\nOUT x\n'
        candidate, _, _ = self.compare(source, error=True)
        self.assertEqual(candidate, source)

    def test_dead_overwrites_are_kept_as_register_lifetime_boundaries(self):
        # Small structural sibling of the coordinator's saved 8x(2000x2000)
        # witness. Do not allocate another ~1GB just to validate the guard.
        source = ('LOAD x,t.x\nHJOIN a,b,x,x\nLOAD a,t.x\nLOAD b,t.x\n'
                  'ISNULL a,x\nIOTA b,x\nSLICE a,x,0\nOUT x\n')
        candidate, _, _ = self.compare(source)
        for line in ['LOAD a,t.x', 'LOAD b,t.x', 'ISNULL a,x', 'IOTA b,x', 'SLICE a,x,0']:
            self.assertIn(line, candidate)

    def test_first_definition_removal_does_not_reclassify_later_overwrite(self):
        source = 'LOAD old,t.s\nLOAD old,t.x\nLOAD x,t.x\nOUT x\n'
        candidate, _, _ = self.compare(source)
        self.assertNotIn('LOAD old,t.s', candidate)
        self.assertIn('LOAD old,t.x', candidate)


if __name__ == '__main__':
    unittest.main()
