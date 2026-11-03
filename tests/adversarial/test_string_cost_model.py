"""Black-box evidence and limits for the direct-LOAD string cost refinement."""

import unittest

import test_join_selection as joins


class StringCostModelReview(unittest.TestCase):
    # Keep every experiment holdout after the simpler active join policy freezes.
    optimizer_command = (str(joins.ROOT / 'experiments/profile_optimizer.py'),)

    setUp = joins.JoinSelectionReview.setUp
    tearDown = joins.JoinSelectionReview.tearDown
    run_vm = joins.JoinSelectionReview.run_vm
    schema = joins.JoinSelectionReview.schema
    optimize = joins.JoinSelectionReview.optimize

    def check(self, left, right, chosen, *, prefix='', flag='', schema=None,
              initial='NLJOIN', raw_cycles=None):
        tables = joins.data(left, right, 'STR', 'STR')
        source = ('LOAD x,l.k\nLOAD y,r.k\n' + prefix + initial +
                  ' a,b,x,y' + flag + '\nOUT a,b\n')
        candidate = self.optimize(source, schema if schema is not None else self.schema(tables))
        self.assertEqual(candidate, source.replace(initial + ' a,b,x,y', chosen + ' a,b,x,y'))
        raw = {}
        reference = None
        for op in ('NLJOIN', 'HJOIN'):
            proc, output = self.run_vm(source.replace(initial + ' a,b,x,y', op + ' a,b,x,y'), tables)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            raw[op] = output['cycles']
            if reference is None:
                reference = output
            else:
                self.assertEqual(output['rows'], reference['rows'])
        proc, selected = self.run_vm(candidate, tables)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(selected['rows'], reference['rows'])
        if raw_cycles:
            self.assertEqual(raw, raw_cycles)
        return raw, selected

    def test_seed_skew_uses_known_empty_frequency(self):
        values = [''] * 63 + ['x' * 10000]
        self.check(values, values, 'NLJOIN',
                   raw_cycles={'NLJOIN': 22180, 'HJOIN': 28852})

    def test_nulls_are_zero_byte_mass_and_nulleq_changes_only_pairs(self):
        values = [None] * 63 + ['x' * 10000]
        self.check(values, values, 'NLJOIN',
                   raw_cycles={'NLJOIN': 14242, 'HJOIN': 20914})
        self.check(values, values, 'NLJOIN', flag=',NULLEQ',
                   raw_cycles={'NLJOIN': 22180, 'HJOIN': 28852})

    def test_utf8_bytes_not_character_count(self):
        self.check(['']*63+['x'*1000], ['']*63+['x'*1000], 'HJOIN',
                   raw_cycles={'NLJOIN': 13180, 'HJOIN': 10852})
        self.check(['']*63+['🙂'*1000], ['']*63+['🙂'*1000], 'NLJOIN',
                   raw_cycles={'NLJOIN': 16180, 'HJOIN': 16852})
        # Both nonempty values occur repeatedly and therefore appear in common.
        self.check(['']*62+['🙂'*1000]*2, ['']*61+['a'*6000]*3, 'HJOIN',
                   raw_cycles={'NLJOIN': 35804, 'HJOIN': 34476})

    def test_rounded_mean_and_zero_residual_mass_are_safe(self):
        # avg .99*199 - common bytes198 = -.99, within +/- .995 rounding.
        values = ['x']*198+['']
        self.check(values, values, 'HJOIN')
        # Every row appears in common; rounded total .04*67 differs from 3 bytes.
        values = ['x']*3+['']*64
        self.check(values, values, 'HJOIN')
        self.check([None]*4, [None]*3, 'NLJOIN')
        self.check([], [], 'NLJOIN')

    def test_residual_singleton_tail_remains_a_model_limitation(self):
        frequent = sum(([chr(65+i)]*4 for i in range(8)), [])
        singles = [chr(i) for i in range(33, 127) if chr(i) not in 'ABCDEFGH'][:31]
        values = frequent + singles + ['x'*10000]
        # Explicit expected regret, not a correctness defect: the mean residual
        # bucket cannot distinguish 31 short singles from one long outlier.
        self.check(values, values, 'HJOIN',
                   raw_cycles={'NLJOIN': 18655, 'HJOIN': 21358})

    def test_truncated_common_tail_is_not_assumed_singleton(self):
        # Ten repeated values exist, but common has only the top eight.
        values = sum(([str(i)*(i+1)]*(20-i) for i in range(10)), [])
        schema = self.schema(joins.data(values, values, 'STR', 'STR'))
        self.assertEqual(len(schema['l']['stats']['columns']['k']['common']), 8)
        self.check(values, values, 'HJOIN', schema=schema)

    def test_rounding_ambiguous_near_tie_retains_original_algorithm(self):
        # Right total is 4023 bytes; rounded mean 4.02 implies a 4020-byte
        # central estimate. Point costs favor NL by2; true costs favor H by1.
        right = [f'{i:04d}' for i in range(977)] + [f'z{i:04d}' for i in range(23)]
        for initial in ('NLJOIN', 'HJOIN'):
            with self.subTest(initial=initial):
                self.check(['zzzzz']*2, right, initial, initial=initial,
                           raw_cycles={'NLJOIN': 11064, 'HJOIN': 11063})

    def test_derived_columns_drop_direct_load_profile(self):
        values = ['']*63+['x'*10000]
        for prefix in ['UPPER x,x\nUPPER y,y\n',
                       'SLICE x,x,64\nSLICE y,y,64\n',
                       'IOTA i,x\nGATHER x,x,i\nIOTA j,y\nGATHER y,y,j\n']:
            with self.subTest(prefix=prefix):
                self.check(values, values, 'HJOIN', prefix=prefix)

    def test_missing_or_inconsistent_profiles_fall_back(self):
        values = ['']*63+['x'*10000]
        tables = joins.data(values, values, 'STR', 'STR')
        for key, chosen in [('common', 'HJOIN'), ('nulls', 'HJOIN'), ('avg_bytes', 'NLJOIN')]:
            schema = self.schema(tables)
            for item in schema.values():
                item['stats']['columns']['k'].pop(key)
            with self.subTest(missing=key):
                self.check(values, values, chosen, schema=schema)
        schema = self.schema(tables)
        for item in schema.values():
            item['stats']['columns']['k']['common'] = [['', 65]]
        self.check(values, values, 'HJOIN', schema=schema)

    def test_stale_length_profile_can_still_regress(self):
        estimated = ['']*63+['x'*10000]
        schema = self.schema(joins.data(estimated, estimated, 'STR', 'STR'))
        # Same declarations, different length/frequency distribution; no schema
        # constraint promises that common values or averages remain unchanged.
        self.check(['x']*64, ['x']*64, 'NLJOIN', schema=schema, initial='HJOIN',
                   raw_cycles={'NLJOIN': 16528, 'HJOIN': 9232})


if __name__ == '__main__':
    unittest.main()
