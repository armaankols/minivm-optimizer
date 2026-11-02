"""Independent harness checks, including real command-interface optimizer mutants."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evaluator as ev


def result(rows, width=None):
    return {'ncols': width if width is not None else (len(rows[0]) if rows else 1),
            'rows': rows, 'cycles': 0}


class ComparisonTests(unittest.TestCase):
    def compare(self, a, b, kinds=('INT',), ordered=False):
        return ev.compare_results(result(a, len(kinds)), result(b, len(kinds)), kinds, ordered)[0]

    def test_bag_permutation(self):
        self.assertTrue(self.compare([[1],[2],[1]], [[2],[1],[1]]))

    def test_multiplicity(self):
        self.assertFalse(self.compare([[1],[1],[2]], [[1],[2],[2]]))

    def test_row_associations(self):
        self.assertFalse(self.compare([[1,'a'],[2,'b']], [[1,'b'],[2,'a']], ('INT','STR')))

    def test_order(self):
        self.assertFalse(self.compare([[1],[2]], [[2],[1]], ordered=True))

    def test_tolerance_requires_augmenting_path(self):
        self.assertTrue(self.compare([['1'],['1.0000015']], [['1.00000075'],['0.99999925']], ('NUM',)))

    def test_numeric_tolerance(self):
        self.assertTrue(self.compare([['100']], [['100.00005']], ('NUM',)))
        self.assertFalse(self.compare([['100']], [['100.01']], ('NUM',)))
        self.assertFalse(self.compare([['0']], [['0.0000000001']], ('NUM',)))
        self.assertTrue(self.compare([['1.0']], [['1.00']], ('NUM',)))

    def test_numeric_slot_rejects_noncanonical_string_payloads(self):
        for text in ['1e1000000', ' 1.0 ', 'NaN', 'Infinity', '1e0', '+1.0', '0'*1000]:
            with self.subTest(text=text):
                self.assertFalse(ev.cell_equal('1.0', text, 'NUM'))

    def test_int_slot_allows_numeric_type_scale_and_relative_tolerance(self):
        self.assertTrue(self.compare([[1]], [['1.0']], ('INT',)))
        self.assertTrue(self.compare([[1]], [['1.0000005']], ('INT',)))
        self.assertFalse(self.compare([[1]], [['1.00001']], ('INT',)))
        self.assertFalse(self.compare([[0]], [['0.0000000001']], ('INT',)))

    def test_bool_is_not_int_including_fast_path(self):
        self.assertFalse(self.compare([[True]], [[1]], ('BOOL',)))
        self.assertFalse(self.compare([[1]], [[True]], ('INT',)))

    def test_numeric_looking_string_is_exact(self):
        self.assertFalse(self.compare([['1.0']], [['1.00']], ('STR',)))

    def test_null_is_not_false_or_zero(self):
        self.assertFalse(self.compare([[None]], [[False]], ('BOOL',)))
        self.assertFalse(self.compare([[None]], [[0]], ('INT',)))

    def test_wide_integer_precision(self):
        a = '170141183460469231731687303715884105727'
        self.assertTrue(self.compare([[a]], [[a]], ('INT',)))
        self.assertFalse(self.compare([[a]], [['170141000000000000000000000000000000000']], ('INT',)))

    def test_shape(self):
        self.assertFalse(ev.compare_results(result([[1]]), result([[1,2]]), ('INT',), False)[0])
        for raw in [b'{}', b'{"ncols":true,"rows":[],"cycles":1}',
                    b'{"ncols":1,"rows":[[1,2]],"cycles":1}',
                    b'{"ncols":1,"rows":[[1.5]],"cycles":1}',
                    b'{"ncols":1,"ncols":1,"rows":[],"cycles":1}',
                    b'{"ncols":1,"rows":[],"cycles":NaN}', b'[]', b'\xff']:
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                ev.parse_result(raw)


class ProcessTests(unittest.TestCase):
    def run_code(self, code, **kwargs):
        return ev.run_process([sys.executable, '-c', code], kwargs.pop('timeout', 1),
                              kwargs.pop('deadline', time.monotonic()+3), **kwargs)

    def test_exit_and_streams(self):
        r = self.run_code('import sys; print("ok"); print("err",file=sys.stderr);sys.exit(7)')
        self.assertEqual((r.returncode,r.stdout,r.stderr,r.issue), (7,b'ok\n',b'err\n',None))

    def test_missing_executable(self):
        r = ev.run_process(['/path/does/not/exist'], 1, time.monotonic()+2)
        self.assertEqual(r.issue, 'could not start subprocess')

    def test_timeout(self):
        self.assertEqual(self.run_code('import time; time.sleep(10)', timeout=.04).issue, 'subprocess timed out')

    def test_output_bounds(self):
        r = self.run_code('import sys; sys.stdout.write("x"*100000)', stdout_limit=1024)
        self.assertEqual(r.issue, 'stdout exceeded byte limit')
        self.assertEqual(len(r.stdout), 1024)
        r = self.run_code('import sys; sys.stderr.write("x"*100000)', stderr_limit=512)
        self.assertEqual(r.issue, 'stderr exceeded byte limit')
        self.assertEqual(len(r.stderr), 512)

    def test_global_deadline_not_optimizer_defect(self):
        with self.assertRaises(ev.EvaluationError):
            self.run_code('import time; time.sleep(10)', timeout=60, deadline=time.monotonic()+.04)

    def test_child_process_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp)/'survived'
            child = 'import time,pathlib;time.sleep(.3);pathlib.Path('+repr(str(marker))+').write_text("bad")'
            parent = 'import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(child)+'])'
            r = self.run_code(parent, timeout=.08)
            self.assertEqual(r.issue, 'subprocess timed out')
            time.sleep(.4)
            self.assertFalse(marker.exists())


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='evaluator-tests-')
        cls.folder = Path(cls.temp.name)
        cls.cases = ev.make_cases()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def optimizer(self, source, name='optimizer with spaces'):
        p = self.folder/name
        p.write_text('#!'+sys.executable+'\n'+source+'\n')
        p.chmod(0o755)
        return p

    def run_optimizer(self, source, cases=None, **kwargs):
        return ev.evaluate(self.optimizer(source), cases=self.cases[:1] if cases is None else cases,
                           artifact_root=self.folder/'failures', **kwargs)

    def test_actual_public_cli_identity_full_suite(self):
        identity = self.optimizer('import sys;sys.stdout.write(open(sys.argv[1]).read())')
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        r = subprocess.run([str(ROOT/'evaluate'),str(identity)], cwd='/tmp', env=env,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr)
        report = json.loads(r.stdout)
        self.assertEqual(report['status'],'no defects found')
        self.assertEqual(report['cases'],len(self.cases))
        self.assertEqual(report['executions'],sum(len(c.datasets) for c in self.cases))

    def test_actual_public_cli_rejects_known_mutant(self):
        mutant = self.optimizer("print('LOAD x,t.x\\nSLICE x,x,0\\nOUT x')")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
        r = subprocess.run([str(ROOT/'evaluate'),str(mutant)], cwd='/tmp', env=env,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=10)
        self.assertEqual(r.returncode,1,r.stdout+r.stderr)
        self.assertIn('optimizer defect:',r.stderr)
        self.assertIn('witness',r.stderr)

    def test_known_mutants_rejected_with_witnesses(self):
        mutants = [
            "print('LOAD x,t.x\\nSLICE x,x,0\\nOUT x')",  # empty output
            "print('LOAD x,t.x\\nLOAD s,t.s\\nOUT s,x')",  # swap columns
            "print('LOAD x,t.x\\nLOAD s,t.s\\nGROUP g,x,s\\nGFIRST i,g\\nGATHER x,x,i\\nGATHER s,s,i\\nOUT x,s')", # duplicate loss
            "print('LOAD x,t.x\\nLOAD s,t.s\\nSORT i,x ASC NF\\nGATHER x,x,i\\nOUT x,s')", # lost row associations
            "import sys;sys.exit(3)",
            "print('not a MiniVM program')",
            "print('')",
            "import sys;sys.stdout.buffer.write(b'\\xff')",
        ]
        for source in mutants:
            with self.subTest(source=source), self.assertRaises(ev.Defect):
                self.run_optimizer(source)
        failures = list((self.folder/'failures').glob('*/failure.json'))
        self.assertGreaterEqual(len(failures),len(mutants))
        for p in failures:
            self.assertIn('message',json.loads(p.read_text()))
            self.assertTrue((p.parent/'original.mini').exists())
            self.assertTrue((p.parent/'data.json').exists())

    def test_external_optimizer_numeric_type_change_is_accepted(self):
        # Confirmed coordinator finding: integer provenance formerly forced
        # integral candidate serialization, falsely rejecting equivalent NUMs.
        data = {'t':ev.table([('x','INT')],[[1],[2],[None]])}
        case = ev.Case('numeric_type_change','LOAD x,t.x\nOUT x\n',('INT',),False,[data])
        source = "print('LOAD x,t.x\\nADD y,x,0.1\\nSUB y,y,0.1\\nOUT y')"
        report = self.run_optimizer(source,[case])
        self.assertEqual(report['executions'],1)

    def test_exponent_string_mutant_has_retained_witness(self):
        # Confirmed coordinator finding: Decimal formerly overflowed here before
        # producing a Defect or retaining the successful candidate VM output.
        mutant = "print(\"LOAD x,t.x\\nLOAD s,t.s\\nFILL bad,'1e1000000',x\\nOUT bad,s\")"
        with self.assertRaisesRegex(ev.Defect, 'witness'):
            self.run_optimizer(mutant)
        numeric_case = next(c for c in self.cases if c.name == 'numeric_values')
        mutant = "print(\"LOAD x,t.x\\nFILL bad,'1e1000000',x\\nOUT bad,bad,bad\")"
        with self.assertRaisesRegex(ev.Defect, 'witness'):
            self.run_optimizer(mutant,[numeric_case])

    def test_order_numeric_and_null_mutants(self):
        choices = [
            ('ordered_rows', "import sys;s=open(sys.argv[1]).read();print(s.replace('x ASC NF','x DESC NL'))"),
            ('numeric_values', "import sys;s=open(sys.argv[1]).read();print(s.replace('DIV b,a,3','DIV b,a,2'))"),
            ('null_logic', "import sys;s=open(sys.argv[1]).read();print(s.replace('EQ e,x,x','IS e,x,x'))"),
            ('string_values', "import sys;s=open(sys.argv[1]).read();print(s.replace('LOAD s,t.s',\"LOAD s,t.s\\nFILL s,'1.00',s\"))"),
        ]
        for name,source in choices:
            with self.subTest(name=name), self.assertRaises(ev.Defect):
                self.run_optimizer(source,[next(c for c in self.cases if c.name==name)])

    def test_timeout_and_flood_mutants(self):
        with self.assertRaises(ev.Defect):
            self.run_optimizer('import time;time.sleep(10)', optimizer_timeout=.04)
        with self.assertRaises(ev.Defect):
            self.run_optimizer('import sys;sys.stdout.write("x"*5000000)')

    def test_frozen_schema_on_changed_valid_data(self):
        source = '''import json,sys
schema=json.load(open(sys.argv[2]))
n=schema['t']['stats']['rows']
print('LOAD x,t.x\\nLOAD s,t.s\\nSLICE x,x,%d\\nSLICE s,s,%d\\nOUT x,s' % (n,n))'''
        case = self.cases[0]
        smaller = {'t':dict(case.datasets[0]['t'], rows=case.datasets[0]['t']['rows'][:1])}
        frozen = ev.Case('stats_are_not_constraints',case.program,case.kinds,False,
                         [smaller,case.datasets[0]])
        with self.assertRaises(ev.Defect):
            self.run_optimizer(source,[frozen])

    def test_alternative_cannot_change_constraints(self):
        case = self.cases[0]
        modified = {'t':dict(case.datasets[0]['t'], check={'x':[-10,10]})}
        bad_case = ev.Case('changed_constraints',case.program,case.kinds,False,
                           [case.datasets[0],modified])
        with self.assertRaisesRegex(ev.EvaluationError,'changes schema constraints'):
            self.run_optimizer('import sys;print(open(sys.argv[1]).read())',[bad_case])

    def test_overall_deadline_is_incomplete(self):
        with self.assertRaises(ev.EvaluationError):
            self.run_optimizer('import sys;print(open(sys.argv[1]).read())',budget=0)

    def test_vm_malformed_and_timeout(self):
        for source in ['print("{}")', 'import time;time.sleep(10)']:
            vm = self.optimizer(source,name='fake-vm')
            with self.subTest(source=source):
                if 'sleep' in source:
                    with self.assertRaises(ev.EvaluationError):
                        ev.run_vm('unused','unused',time.monotonic()+.04,vm)
                else:
                    with self.assertRaises(ValueError):
                        ev.run_vm('unused','unused',time.monotonic()+1,vm)


if __name__ == '__main__':
    unittest.main()
