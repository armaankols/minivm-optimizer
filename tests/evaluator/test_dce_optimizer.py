"""Black-box tests for proven-total DCE through required two-argument CLI.

Success/error and exact output come from original MiniVM execution. Join-only
mode isolates the preceding stage when checking that DCE only blanks lines.
No optimizer implementation imports or estimates establish expected behavior.
"""
import json
from pathlib import Path
import re
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import evaluator as ev


def fixture(rows=None,other=None):
    if rows is None:
        rows=[[1,' ab ','2024-02-29'],[None,None,None],[2,'straße','9999-12-31']]
    if other is None:
        other=[[1],[None],[2]]
    return {'t':ev.table([('x','INT'),('s','STR'),('d','DATE')],rows),
            'u':ev.table([('x','INT')],other)}


def run(argv,deadline):
    result=ev.run_process(argv,60,deadline)
    if result.issue:
        raise AssertionError((result.issue,result.stderr[:500]))
    return result


def instruction_lines(source):
    # These fixtures avoid semicolons inside literals. LF only, preserving
    # Unicode separators as literal text rather than invented instructions.
    return [line.strip() for line in source.split(b'\n')
            if line.strip() and not line.lstrip().startswith(b';')]


class DeadCodeInterfaceTests(unittest.TestCase):
    def check(self,source,datasets,*,removed=(),retained=(),all_removed=False):
        source=source.encode('utf8') if isinstance(source,str) else source
        with tempfile.TemporaryDirectory(prefix='dce-interface-') as directory:
            directory=Path(directory)
            original=directory/'original.mini'
            candidate=directory/'candidate.mini'
            join_only=directory/'joins-only.mini'
            data_file=directory/'data.json'
            schema_file=directory/'schema.json'
            original.write_bytes(source)
            data_file.write_text(json.dumps(datasets[0]))
            deadline=time.monotonic()+65
            schema=run([ROOT/'bin/minivm','--schema',data_file],deadline)
            self.assertEqual(schema.returncode,0,schema.stderr)
            schema_file.write_bytes(schema.stdout)
            stage=run([ROOT/'optimize','--joins-only',original,schema_file],deadline)
            selected=run([ROOT/'optimize',original,schema_file],deadline)
            self.assertEqual(stage.returncode,0,stage.stderr)
            self.assertEqual(selected.returncode,0,selected.stderr)
            join_only.write_bytes(stage.stdout)
            candidate.write_bytes(selected.stdout)
            before_lines,after_lines=stage.stdout.split(b'\n'),selected.stdout.split(b'\n')
            self.assertEqual(len(before_lines),len(after_lines),'DCE changed line count')
            for before,after in zip(before_lines,after_lines):
                self.assertEqual(before.endswith(b'\r'),after.endswith(b'\r'),'CRLF changed')
                if before!=after:
                    self.assertTrue(not after.strip() or after.lstrip().startswith(b';'),
                                    'DCE changed a retained instruction')
            for text in removed:
                self.assertNotIn(text.encode(),selected.stdout)
            for text in retained:
                self.assertIn(text.encode(),selected.stdout)
            if all_removed:
                self.assertEqual(instruction_lines(selected.stdout),[b'LOAD x,t.x',b'OUT x'])
            cycle_pairs=[]
            for data in datasets:
                data_file.write_text(json.dumps(data))
                baseline=run([ROOT/'bin/minivm',original,data_file],deadline)
                actual=run([ROOT/'bin/minivm',candidate,data_file],deadline)
                self.assertEqual(actual.returncode,baseline.returncode,(baseline.stderr,actual.stderr))
                if baseline.returncode==0:
                    a,b=ev.parse_result(baseline.stdout),ev.parse_result(actual.stdout)
                    self.assertEqual((a['ncols'],a['rows']),(b['ncols'],b['rows']))
                    cycle_pairs.append((a['cycles'],b['cycles']))
                else:
                    self.assertEqual(baseline.returncode,1)
                    self.assertEqual(actual.stdout,b'')
            return selected.stdout,cycle_pairs

    def test_total_whitelist_eliminates_dead_leaf_work_and_loads(self):
        source='''LOAD x,t.x
LOAD s,t.s
UPPER up,s
RTRIM rt,s
TRIM tr,s
LEN size,s
NULLIFE nil,s
LEFT left_s,s,2
SUBSTR middle,s,1,3
ISNULL mask,s
IOTA positions,s
SLICE prefix,s,2
LOAD d,t.d
YEAR yr,d
MONTH mo,d
DAY dy,d
DOW weekday,d
OUT x
'''
        _,cycles=self.check(source,[fixture(),fixture([],[]),fixture([[None,None,None]],[[None]])],all_removed=True)
        self.assertTrue(all(after<before for before,after in cycles))

    def test_dead_first_definition_before_live_overwrite_is_removed(self):
        source='LOAD x,t.s\nLOAD x,t.x\nOUT x\n'
        self.check(source,[fixture()],removed=['LOAD x,t.s'],retained=['LOAD x,t.x','OUT x'])

    def test_dead_join_output_overwrites_are_retained_for_register_lifetimes(self):
        # Saved full witness uses2000x2000constant keys and8fresh joins. Removing
        # these overwrite LOADs leaves large old position columns resident and
        # makes a successful original exceed the64M aggregate register limit.
        # Tiny values check the guard without repeating the1GB resource probe.
        lines=['LOAD x,t.x']
        overwrites=[]
        for i in range(8):
            lines.append(f'HJOIN a{i},b{i},x,x')
            for name in (f'a{i}',f'b{i}'):
                line=f'LOAD {name},t.x'
                lines.append(line)
                overwrites.append(line)
        lines.append('OUT x')
        source='\n'.join(lines)+'\n'
        small=fixture([[1,'a','2024-01-01'],[1,'b','2024-01-01']],[[1],[1]])
        emitted,_=self.check(source,[small,fixture([],[])],retained=overwrites)
        self.assertEqual(len(instruction_lines(emitted)),len(lines))

    def test_dead_unary_self_overwrites_are_retained_for_register_lifetimes(self):
        source='LOAD s,t.s\nUPPER s,s\nLEN s,s\nIOTA s,s\nSLICE s,s,0\nLOAD x,t.x\nOUT x\n'
        self.check(source,[fixture(),fixture([],[])],retained=[
            'LOAD s,t.s','UPPER s,s','LEN s,s','IOTA s,s','SLICE s,s,0'])

    def test_reassignment_retains_prewrite_dependencies_and_failures(self):
        source='LOAD x,t.x\nDIV x,x,0\nLOAD x,t.s\nOUT x\n'
        self.check(source,[fixture([[None,None,None]],[[None]]),fixture([[1,'a','2024-01-01']],[[1]])],
                   retained=['LOAD x,t.x','DIV x,x,0','LOAD x,t.s'])

    def test_dead_division_and_type_errors_under_null_masks_are_retained(self):
        for operation in ['DIV bad,x,0','ADD bad,s,1','LEFT bad,x,2','IF bad,x,1,2']:
            source='LOAD x,t.x\nLOAD s,t.s\n'+operation+'\nOUT x\n'
            with self.subTest(operation=operation):
                self.check(source,[fixture([[None,None,None]],[[None]]),fixture([[1,'str','2024-01-01']],[[1]])],
                           retained=[operation])

    def test_dead_cross_table_length_mismatch_is_retained(self):
        source='LOAD x,t.x\nLOAD y,u.x\nNVL bad,x,y\nOUT x\n'
        rows=[[1,'a','2024-01-01'],[2,'b','2024-01-02']]
        self.check(source,[fixture(rows,[[1],[2]]),fixture(rows,[[1],[2],[3]])],
                   retained=['LOAD y,u.x','NVL bad,x,y'])

    def test_dead_numeric_overflow_and_date_range_errors_are_retained(self):
        source='LOAD x,t.x\nMUL bad,x,170141183460469231731687303715884105727\nOUT x\n'
        self.check(source,[fixture([[1,'s','2024-01-01']],[[1]]),fixture([[2,'s','2024-01-01']],[[1]])],
                   retained=['MUL bad,x,170141183460469231731687303715884105727'])
        source='LOAD x,t.x\nLOAD d,t.d\nDATEADD bad,d,1\nOUT x\n'
        self.check(source,[fixture([[1,'s','2024-01-01']],[[1]]),fixture([[1,'s','9999-12-31']],[[1]])],
                   retained=['DATEADD bad,d,1'])

    def test_unmodeled_writes_invalidate_previous_type_fact(self):
        source='LOAD s,t.s\nFILL s,1,s\nUPPER bad,s\nLOAD x,t.x\nOUT x\n'
        self.check(source,[fixture([],[]),fixture()],retained=['FILL s,1,s','UPPER bad,s','LOAD s,t.s'])
        source='LOAD x,t.s\nLOAD x,t.x\nLEN bad,x\nOUT x\n'
        self.check(source,[fixture([[None,None,None]],[[None]]),fixture()],retained=['LEN bad,x','LOAD x,t.x'])

    def test_group_register_overwrite_invalidates_column_fact(self):
        for operation in ['IOTA bad,x','ISNULL bad,x','SLICE bad,x,1']:
            source='LOAD x,t.x\nGROUP x,x\n'+operation+'\nLOAD answer,t.x\nOUT answer\n'
            with self.subTest(operation=operation):
                self.check(source,[fixture([],[]),fixture()],retained=['GROUP x,x',operation])

    def test_dead_gather_out_of_range_and_empty_gall_first_are_retained(self):
        source='LOAD x,t.x\nFILL indexes,999,x\nGATHER bad,x,indexes\nOUT x\n'
        self.check(source,[fixture([],[]),fixture()],retained=['FILL indexes,999,x','GATHER bad,x,indexes'])
        source='LOAD x,t.x\nGALL g,x\nGFIRST i,g\nGATHER bad,x,i\nOUT x\n'
        self.check(source,[fixture(),fixture([],[])],retained=['GATHER bad,x,i'])

    def test_invalid_source_and_counts_are_not_erased(self):
        for operation in ['LOAD bad,t.missing','SLICE bad,x,-1','SUBSTR bad,s,0,1','LEFT bad,s,-1']:
            source='LOAD x,t.x\nLOAD s,t.s\n'+operation+'\nOUT x\n'
            with self.subTest(operation=operation):
                self.check(source,[fixture()],retained=[operation])

    def test_output_order_types_duplicate_columns_and_multiplicity(self):
        source='LOAD x,t.x\nLOAD s,t.s\nLOAD dead,t.d\nLEN unused,s\nOUT s,x,x\n'
        rows=[[1,'z','2024-01-01'],[1,'a','2024-01-01'],[None,None,None],[1,'z','2024-01-01']]
        self.check(source,[fixture(rows)],removed=['LOAD dead,t.d','LEN unused,s'],retained=['OUT s,x,x'])

    def test_live_self_reassignment_and_join_alias_operands_are_retained(self):
        source='LOAD x,t.x\nIOTA x,x\nOUT x\n'
        self.check(source,[fixture(),fixture([],[])],retained=['LOAD x,t.x','IOTA x,x','OUT x'])
        source='LOAD a,t.x\nLOAD b,u.x\nHJOIN a,a,a,b\nLOAD answer,t.x\nOUT answer\n'
        emitted,_=self.check(source,[fixture(),fixture([],[])],retained=['LOAD a,t.x','LOAD b,u.x'])
        self.assertRegex(emitted.decode(),r'(?:HJOIN|NLJOIN) a,a,a,b')

    def test_unknown_opcode_or_syntax_falls_back_for_whole_dce_pass(self):
        for operation in ['MYSTERY bad,x','LEN broken']:
            source='LOAD x,t.x\nLOAD unused,t.s\n'+operation+'\nOUT x\n'
            with self.subTest(operation=operation):
                self.check(source,[fixture()],retained=['LOAD unused,t.s',operation])

    def test_comments_crlf_and_no_final_newline_remain_reviewable(self):
        source=b'; heading\r\nLOAD x,t.x\r\nLOAD unused,t.s ; dead display\r\nLEN n,unused\r\nOUT x'
        emitted,_=self.check(source,[fixture()],removed=['LOAD unused,t.s','LEN n,unused'],retained=['; heading'])
        self.assertEqual(emitted.count(b'\r\n'),4)
        self.assertTrue(emitted.endswith(b'OUT x'))


if __name__=='__main__':
    unittest.main()
