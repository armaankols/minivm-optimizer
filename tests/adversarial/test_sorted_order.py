"""Independent public-command tests for one guaranteed-order rewrite only."""

import json
import subprocess
import unittest

import test_join_selection as joins


def ordered_tables(empty=False):
    return {
        't': {'columns': [{'name': 'a', 'type': 'INT'}, {'name': 'b', 'type': 'INT'},
                          {'name': 's', 'type': 'STR'}], 'sorted': ['a', 'b'],
              'rows': [] if empty else [[None, None, 'u'], [None, 1, 'v'],
                                        [1, None, 'w'], [1, 2, 'z'],
                                        [1, 2, 'a'], [2, 0, 'q']]},
        'u': {'columns': [{'name': 'b', 'type': 'INT'}],
              'rows': [] if empty else [[2], [1], [None], [1], [None], [0]]},
    }


class SortedOrderReview(unittest.TestCase):
    setUp = joins.JoinSelectionReview.setUp
    tearDown = joins.JoinSelectionReview.tearDown
    run_vm = joins.JoinSelectionReview.run_vm
    schema = joins.JoinSelectionReview.schema

    def optimize(self, source, schema, *, baseline=False):
        path, schema_path = self.folder / 'original.mini', self.folder / 'schema.json'
        path.write_bytes(source.encode())
        schema_path.write_text(json.dumps(schema))
        command = [str(joins.ROOT / 'optimize')]
        if baseline:
            command.append('--no-sorted-order')
        proc = subprocess.run([*command, str(path), str(schema_path)],
                              capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout.decode()

    def compare(self, source, tables=None, *, schema=None, error=False):
        tables = ordered_tables() if tables is None else tables
        candidate = self.optimize(source, self.schema(tables) if schema is None else schema)
        old, before = self.run_vm(source, tables)
        new, after = self.run_vm(candidate, tables)
        if error:
            self.assertEqual((old.returncode, new.returncode), (1, 1), (old.stderr, new.stderr))
            self.assertEqual(old.stdout, '')
            self.assertEqual(new.stdout, '')
        else:
            self.assertEqual((old.returncode, new.returncode), (0, 0), (old.stderr, new.stderr))
            self.assertEqual(before['ncols'], after['ncols'])
            self.assertEqual(before['rows'], after['rows'])
        self.assertEqual(candidate.count('\n'), source.count('\n'))
        return candidate, before, after

    def assert_sort_kept(self, candidate, destination='i'):
        self.assertTrue(any(line.strip().upper().startswith('SORT '+destination.upper()+',')
                            for line in candidate.split('\n')), candidate)

    def assert_iota(self, candidate, destination='i', source='a'):
        for line in candidate.split('\n'):
            code = line.split(';', 1)[0].strip()
            if code and code.split()[0].upper() == 'IOTA':
                opcode, rest = code.split(None, 1)
                if [x.strip() for x in rest.split(',')] == [destination, source]:
                    return
        self.fail('missing IOTA '+destination+','+source+' in '+candidate)

    def test_full_and_short_prefix_nullable_ties_preserve_identity(self):
        for keys in ['a ASC NF', 'a ASC NF,b ASC NF']:
            with self.subTest(keys=keys):
                source = 'LOAD a,t.a\nLOAD b,t.b\nLOAD s,t.s\nSORT i,'+keys+'\nOUT i,a,b,s\n'
                candidate, before, after = self.compare(source)
                self.assert_iota(candidate)
                self.assertEqual([row[0] for row in after['rows']], list(range(6)))
                self.assertLess(after['cycles'], before['cycles'])

    def test_empty_snapshot_and_empty_runtime_are_both_safe(self):
        source = 'LOAD a,t.a\nLOAD b,t.b\nSORT i,a ASC NF,b ASC NF\nOUT i\n'
        schema = self.schema(ordered_tables(empty=True))
        for tables in [ordered_tables(empty=True), ordered_tables()]:
            with self.subTest(empty=not tables['t']['rows']):
                candidate, _, _ = self.compare(source, tables, schema=schema)
                self.assert_iota(candidate)

    def test_num_scale_equal_values_and_utf8_strings_keep_tie_order(self):
        for kind, values in [('NUM', [None, '0.00', '1.00', '1.0', '1.000', '2']),
                             ('STR', [None, '', 'a', 'a', 'é', '🙂'])]:
            tables = {'t': {'columns': [{'name': 'a', 'type': kind}],
                            'sorted': ['a'], 'rows': [[x] for x in values]}}
            with self.subTest(kind=kind):
                candidate, _, after = self.compare('LOAD a,t.a\nSORT i,a ASC NF\nOUT i,a\n', tables)
                self.assert_iota(candidate)
                self.assertEqual([row[0] for row in after['rows']], list(range(len(values))))

    def test_suffix_extra_keys_desc_and_nulls_last_are_not_rewritten(self):
        for keys in ['b ASC NF', 'a ASC NF,b ASC NF,s ASC NF', 'a DESC NF', 'a ASC NL']:
            with self.subTest(keys=keys):
                source = 'LOAD a,t.a\nLOAD b,t.b\nLOAD s,t.s\nSORT i,'+keys+'\nOUT i\n'
                candidate, _, _ = self.compare(source)
                self.assert_sort_kept(candidate)

    def test_mixed_tables_equal_statistics_do_not_prove_order(self):
        source = 'LOAD a,t.a\nLOAD b,u.b\nSORT i,a ASC NF,b ASC NF\nOUT i\n'
        candidate, _, _ = self.compare(source)
        self.assert_sort_kept(candidate)

    def test_latest_definition_and_all_unmodeled_writes_invalidate_origins(self):
        sources = [
            'LOAD a,t.a\nLOAD a,t.b\nSORT i,a ASC NF\nOUT i\n',
            'LOAD a,t.a\nIOTA a,a\nSORT i,a ASC NF\nOUT i\n',
            "LOAD a,t.a\nFILL a,1,a\nSORT i,a ASC NF\nOUT i\n",
            'LOAD a,t.a\nLOAD b,t.b\nHJOIN a,b,a,a\nSORT i,b ASC NF\nOUT i\n',
        ]
        for source in sources:
            with self.subTest(source=source):
                candidate, _, _ = self.compare(source)
                self.assert_sort_kept(candidate)
        strings = {'t': {'columns': [{'name': 's', 'type': 'STR'}],
                         'sorted': ['s'], 'rows': [[' a'], [' b'], ['a']]}}
        source = 'LOAD s,t.s\nTRIM s,s\nSORT i,s ASC NF\nOUT i,s\n'
        candidate, _, _ = self.compare(source, strings)
        self.assert_sort_kept(candidate)

    def test_sort_destination_alias_reads_old_key_and_invalidates_origin(self):
        for dest in ['a', 'b']:
            with self.subTest(dest=dest):
                source = ('LOAD a,t.a\nLOAD b,t.b\nSORT '+dest+
                          ',a ASC NF,b ASC NF\nOUT '+dest+'\n')
                candidate, _, _ = self.compare(source)
                self.assert_iota(candidate, destination=dest)
        source = 'LOAD a,t.a\nSORT a,a ASC NF\nSORT i,a ASC NF\nOUT i\n'
        candidate, _, _ = self.compare(source)
        self.assert_iota(candidate, destination='a')
        self.assert_sort_kept(candidate)

    def test_overwrites_remain_lifetime_boundaries_after_secondary_key_unused(self):
        source = ('LOAD x,t.a\nHJOIN a,b,x,x\nLOAD a,t.a\nLOAD b,t.b\n'
                  'SORT b,a ASC NF,b ASC NF\nOUT x\n')
        candidate, _, _ = self.compare(source)
        self.assert_iota(candidate, destination='b')
        self.assertIn('LOAD a,t.a', candidate)
        self.assertIn('LOAD b,t.b', candidate)

    def test_dce_may_remove_dead_first_definition_iota_but_not_gather(self):
        source = 'LOAD a,t.a\nLOAD b,t.b\nLOAD s,t.s\nSORT i,a ASC NF,b ASC NF\nOUT s\n'
        tables = ordered_tables()
        schema = self.schema(tables)
        baseline = self.optimize(source, schema, baseline=True)
        candidate, before, after = self.compare(source, tables, schema=schema)
        self.assert_sort_kept(baseline)
        self.assertNotIn('IOTA', candidate.upper())
        self.assertNotIn('SORT', candidate.upper())
        self.assertLess(after['cycles'], before['cycles'])
        source = 'LOAD a,t.a\nSORT i,a ASC NF\nGATHER o,a,i\nOUT o\n'
        candidate, _, _ = self.compare(source)
        self.assert_iota(candidate)
        self.assertIn('GATHER o,a,i', candidate)

    def test_casefold_only_table_and_column_names_not_registers(self):
        source = 'load A,T.A\nload a,t.B\nsort i,A asc nf,a Asc Nf\nout i,A,a\n'
        candidate, _, _ = self.compare(source)
        self.assert_iota(candidate, source='A')

    def test_statistics_sorted_sample_without_constraint_is_insufficient(self):
        tables = ordered_tables()
        tables['t'].pop('sorted')
        source = 'LOAD a,t.a\nSORT i,a ASC NF\nOUT i\n'
        candidate, _, _ = self.compare(source, tables)
        self.assert_sort_kept(candidate)

    def test_invalid_order_proofs_are_ignored(self):
        source = 'LOAD a,t.a\nSORT i,a ASC NF\nOUT i\n'
        for declaration in [[], 'a', ['absent'], ['a', 'a'], [None]]:
            schema = self.schema(ordered_tables())
            schema['t']['sorted'] = declaration
            with self.subTest(declaration=declaration):
                candidate, _, _ = self.compare(source, schema=schema)
                self.assert_sort_kept(candidate)

    def test_erroring_and_unknown_programs_do_not_gain_order_proofs(self):
        for source in ['LOAD a,t.a\nSORT i,undefined ASC NF\nOUT i\n',
                       'LOAD a,t.a\nGROUP a,a\nSORT i,a ASC NF\nOUT i\n',
                       'LOAD a,t.a\nSORT i,a ASC\nOUT i\n',
                       'LOAD a,t.a\nMYSTERY a,a\nSORT i,a ASC NF\nOUT i\n',
                       'LOAD a,t.a\nSORT i,a ASC NF\nMYSTERY a,a\nOUT i\n']:
            with self.subTest(source=source):
                candidate, _, _ = self.compare(source, error=True)
                self.assert_sort_kept(candidate)

    def test_python_only_whitespace_does_not_hide_sort_key_parse_error(self):
        for separator in ['\x1c', '\x1d', '\x1e', '\x1f']:
            for key in ['a'+separator+'ASC NF', 'a ASC NF'+separator]:
                with self.subTest(separator=repr(separator), key=key):
                    source = 'LOAD a,t.a\nSORT i,'+key+'\nOUT i\n'
                    candidate, _, _ = self.compare(source, error=True)
                    self.assert_sort_kept(candidate)

    def test_unicode_long_s_is_not_ascii_asc_keyword(self):
        source = 'LOAD a,t.a\nSORT i,a AſC NF\nOUT i\n'
        candidate, _, _ = self.compare(source, error=True)
        self.assert_sort_kept(candidate)

    def test_live_source_bytes_comments_and_control_separators_survive(self):
        for separator in ['\r', '\v', '\f', '\x1c', '\x1d', '\x1e', '\x1f', '\u0085', '\u2028', '\u2029']:
            source = ("LOAD a,t.a\r\nLOAD b,t.b\r\nFILL text,'it''s;"+separator+
                      'SORT fake,a ASC NF'+separator+"data',a\r\n\t SoRt i , a ASC NF , b ASC NF ; café sort\r\nOUT i,a,b,text")
            with self.subTest(separator=repr(separator)):
                candidate, _, _ = self.compare(source)
                self.assert_iota(candidate)
                self.assertIn('; café sort\r\n', candidate)
                self.assertEqual(candidate.count('\r\n'), source.count('\r\n'))
                self.assertFalse(candidate.endswith('\n'))
                # Non-rewritten physical lines are all live or nonwhitelist.
                old_lines, new_lines = source.split('\n'), candidate.split('\n')
                self.assertEqual(old_lines[:3], new_lines[:3])
                self.assertEqual(old_lines[4:], new_lines[4:])


if __name__ == '__main__':
    unittest.main()
