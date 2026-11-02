"""Black-box join-only optimizer contract tests; no optimizer imports.

Expected result/error comes exclusively from MiniVM on the original program.
Schema stats are frozen for each optimization and changed under subsequent runs.
Opcode-only source assertions apply specifically to this authorized milestone.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evaluator as ev


def dataset(left, right, left_type='INT', right_type=None):
    return {'l':ev.table([('k',left_type)],[[x] for x in left]),
            'r':ev.table([('k',right_type or left_type)],[[x] for x in right])}


def program(op='NLJOIN', flag='', join='li,ri,a,b', prefix='', suffix='OUT li,ri'):
    return 'LOAD a,l.k\nLOAD b,r.k\n'+prefix+op+' '+join+flag+'\n'+suffix+'\n'


def instructions(source):
    """Small independent tokenizer for the deliberately simple fixtures here."""
    result=[]
    for line in source.splitlines():
        line=line.split(';',1)[0].strip()
        if line:
            op,args=line.split(None,1)
            result.append((op.upper(),tuple(x.strip() for x in args.split(','))))
    return result


class JoinOptimizerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='join-interface-tests-')
        cls.folder=Path(cls.temp.name)
        cls.counter=0

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def check(self, source, datasets, expected_op=None, optimizer=None):
        type(self).counter+=1
        folder=self.folder/str(self.counter)
        folder.mkdir()
        original=folder/'original.mini'
        candidate=folder/'candidate.mini'
        data=folder/'data.json'
        schema=folder/'schema.json'
        original.write_text(source)
        data.write_text(json.dumps(datasets[0]))
        deadline=time.monotonic()+65
        s=ev.run_process([ROOT/'bin/minivm','--schema',data],10,deadline)
        self.assertEqual((s.issue,s.returncode),(None,0),s.stderr)
        schema.write_bytes(s.stdout)
        emitted=ev.run_process([optimizer or ROOT/'optimize',original,schema],60,deadline)
        self.assertEqual((emitted.issue,emitted.returncode),(None,0),emitted.stderr)
        output=emitted.stdout.decode('utf8')
        candidate.write_text(output)
        before,after=instructions(source),instructions(output)
        self.assertEqual(len(before),len(after),'join-only pass changed instruction count')
        for (oldop,oldargs),(newop,newargs) in zip(before,after):
            self.assertEqual(oldargs,newargs,'join-only pass changed operands/flags')
            if oldop in ('NLJOIN','HJOIN'):
                self.assertIn(newop,('NLJOIN','HJOIN'))
                if expected_op:
                    self.assertEqual(newop,expected_op)
            else:
                self.assertEqual(oldop,newop,'join-only pass changed unrelated instruction')
        pairs=[]
        for item in datasets:
            data.write_text(json.dumps(item))
            validity=ev.run_process([ROOT/'bin/minivm','--schema',data],10,deadline)
            self.assertEqual((validity.issue,validity.returncode),(None,0),validity.stderr)
            original_result=ev.run_process([ROOT/'bin/minivm',original,data],10,deadline)
            candidate_result=ev.run_process([ROOT/'bin/minivm',candidate,data],10,deadline)
            self.assertIsNone(original_result.issue)
            self.assertIsNone(candidate_result.issue)
            self.assertEqual(original_result.returncode,candidate_result.returncode,
                             (original_result.stderr,candidate_result.stderr))
            if original_result.returncode==0:
                a,b=ev.parse_result(original_result.stdout),ev.parse_result(candidate_result.stdout)
                self.assertEqual(a['ncols'],b['ncols'])
                self.assertEqual(a['rows'],b['rows'],'join pair positions/order changed')
                pairs.append((a['cycles'],b['cycles']))
            else:
                self.assertEqual(original_result.returncode,1)
                self.assertEqual(candidate_result.stdout,b'')
        return pairs

    def test_tiny_numeric_hash_to_nested(self):
        costs=self.check(program('HJOIN'),[dataset([1,2],[2,1,2])],expected_op='NLJOIN')
        self.assertLess(costs[0][1],costs[0][0])

    def test_large_numeric_nested_to_hash(self):
        d=dataset(list(range(64)),list(reversed(range(64))))
        costs=self.check(program(),[d],expected_op='HJOIN')
        self.assertLess(costs[0][1],costs[0][0])

    def test_string_bytes_can_favor_nested_at_moderate_row_counts(self):
        d=dataset(['x'*1024+str(i) for i in range(32)],['x']*32,'STR')
        costs=self.check(program('HJOIN'),[d],expected_op='NLJOIN')
        self.assertLess(costs[0][1],costs[0][0])

    def test_long_strings_large_join_favors_hash(self):
        values=['x'*80+str(i) for i in range(64)]
        costs=self.check(program(),[dataset(values,list(reversed(values)),'STR')],expected_op='HJOIN')
        self.assertLess(costs[0][1],costs[0][0])

    def test_frozen_stats_do_not_constrain_runtime_data(self):
        baseline=dataset(list(range(64)),list(range(64)))
        alternatives=[baseline,dataset([],[]),dataset([None,1,1],[1,None,1,1]),
                      dataset([9],[9]),dataset([1]*20,[1]*20)]
        self.check(program(),alternatives,expected_op='HJOIN')

    def test_frozen_zero_stats_can_become_nonempty(self):
        self.check(program('HJOIN'),[dataset([],list(range(30))),
                   dataset([1,1,None],[1,None,1])],expected_op='NLJOIN')

    def test_null_duplicates_and_nulleq(self):
        for op in ('NLJOIN','HJOIN'):
            for flag in ('',',NULLEQ'):
                with self.subTest(op=op,flag=flag):
                    self.check(program(op,flag),[dataset([None,1,1,2],[1,None,1,None]),
                                               dataset([],[]),dataset([None],[None])])

    def test_empty_side_and_null_only(self):
        for l,r in [([],[]),([],[1,2]),([1,2],[]),([None]*3,[None]*2)]:
            for op in ('NLJOIN','HJOIN'):
                with self.subTest(l=l,r=r,op=op):
                    self.check(program(op),[dataset(l,r)])

    def test_numeric_cross_type_scale_and_precision(self):
        self.check(program(),[dataset([1,2,None,-2],['1.00','2.000',None,'-2.0','1.0000000000000000000000000001'],'INT','NUM'),
                              dataset([],[],'INT','NUM')])

    def test_derived_wide_int_keys_compare_without_decimal_coercion(self):
        src=program(prefix='MUL a,a,1000000000000000000000000000000\n')
        self.check(src,[dataset([1,0,-1,None],['0','9999999999999999999999999999',None],'INT','NUM')])
        src=program(prefix='MUL a,a,1000000000000000000000000000000\nMUL b,b,1000000000000000000000000000000\n')
        self.check(src,[dataset([1,1,0,None],[1,0,None])])

    def test_numeric_overflow_error_is_preserved(self):
        src=program(prefix='MUL a,a,170141183460469231731687303715884105727\n')
        self.check(src,[dataset([2],[1]),dataset([None],[1])])

    def test_mixed_key_runtime_error_is_preserved(self):
        # BOOL condition derived explicitly so original error is comparison type.
        src=program(prefix="EQ c,a,1\nIF a,c,'str',1\n")
        self.check(src,[dataset([1,2],[1,2]),dataset([None],[None])])

    def test_destination_aliases_and_register_reassignment(self):
        variants=[
            program(join='a,b,a,b',suffix='OUT a,b'),
            program(join='i,i,a,b',suffix='OUT i'),
            program(prefix='LOAD a,r.k\n',join='a,ri,a,b',suffix='OUT a,ri'),
            program(prefix='IOTA a,a\n',join='li,b,a,b',suffix='OUT li,b'),
        ]
        for source in variants:
            with self.subTest(source=source):
                self.check(source,[dataset([1,2,1,None],[2,1,None]),dataset([],[])])

    def test_comment_case_tabs_and_optional_flag_preserved(self):
        source='load\ta,l.k\nload b,r.k\nhjoin\tli, ri, a, b, NULLEQ ; preserve flag\nout li,ri\n'
        self.check(source,[dataset([None,1],[1,None])],expected_op='NLJOIN')

    def test_public_evaluator_rejects_join_mutants(self):
        data=dataset([None,1,1],[1,None,1])
        case=ev.Case('join_mutant_nulleq',program(flag=',NULLEQ'),('INT','INT'),True,[data])
        for name,body in [
            ('drop_flag',"s=s.replace(',NULLEQ','')"),
            ('swap_outputs',"s=s.replace('OUT li,ri','OUT ri,li')"),
        ]:
            executable=self.folder/name
            executable.write_text('#!'+sys.executable+'\nimport sys\ns=open(sys.argv[1]).read()\n'+body+'\nprint(s)\n')
            executable.chmod(0o755)
            with self.subTest(name=name),self.assertRaises(ev.Defect):
                ev.evaluate(executable,cases=[case],artifact_root=self.folder/'failures')


if __name__=='__main__':
    unittest.main()
