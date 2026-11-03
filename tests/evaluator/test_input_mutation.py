"""Regression: optimizer input mutation must never mutate the baseline oracle.

The subprocess can use ordinary in-place writes, replacement, unlink or mode
changes. This is source isolation, not a sandbox against malicious same-user code.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import evaluator as ev


class InputMutationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='input-mutation-tests-')
        self.folder=Path(self.temp.name)
        self.numeric_case=next(c for c in ev.make_cases() if c.name=='numeric_values')

    def tearDown(self):
        self.temp.cleanup()

    def optimizer(self,body,name):
        path=self.folder/name
        path.write_text('#!'+sys.executable+'\nimport sys\nfrom pathlib import Path\n'
                        'p=Path(sys.argv[1])\n'+body+'\n')
        path.chmod(0o755)
        return path

    def public_cli(self,optimizer):
        return subprocess.run([str(ROOT/'evaluate'),str(optimizer)],cwd='/tmp',
                              env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),
                              capture_output=True,text=True,timeout=30)

    def check_pristine_witness(self,folder):
        self.assertEqual((folder/'original.mini').read_text(),self.numeric_case.program)
        self.assertIn('DIV b,a,3',(folder/'original.mini').read_text())
        self.assertIn('DIV b,a,2',(folder/'optimized.mini').read_text())
        receipt=json.loads((folder/'failure.json').read_text())
        original=ev.run_vm(folder/'original.mini',folder/'data.json',
                           time.monotonic()+10,ROOT/'bin/minivm')
        candidate=ev.run_vm(folder/'optimized.mini',folder/'data.json',
                            time.monotonic()+10,ROOT/'bin/minivm')
        self.assertEqual(receipt['expected'],original)
        self.assertEqual(receipt['actual'],candidate)
        self.assertNotEqual(original['rows'],candidate['rows'])

    def test_public_cli_rejects_wrong_rewrite_with_or_without_input_mutation(self):
        # Exact review witness: both executables print the same wrong source.
        for mutating in (False,True):
            body="s=p.read_text().replace('DIV b,a,3','DIV b,a,2')\n"
            if mutating:
                body+='p.write_text(s)\n'
            body+='sys.stdout.write(s)'
            optimizer=self.optimizer(body,'inplace-wrong' if mutating else 'stdout-wrong')
            with self.subTest(mutating=mutating):
                result=self.public_cli(optimizer)
                self.assertEqual(result.returncode,1,result.stdout+result.stderr)
                self.assertIn('numeric_values: unordered rows differ',result.stderr)
                witness=Path(result.stderr.split('; witness ',1)[1].strip())
                self.check_pristine_witness(witness)

    def test_public_cli_accepts_inplace_identity_with_readonly_source(self):
        # New case-local input files prevent this0400 mode from contaminating
        # the next case, while the baseline has its own untouched file.
        optimizer=self.optimizer('s=p.read_text()\np.write_text(s)\np.chmod(0o400)\nsys.stdout.write(s)',
                                 'readonly-inplace-identity')
        result=self.public_cli(optimizer)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual((report['cases'],report['executions']),(26,70))

    def test_optimizer_can_remove_its_input_after_reading(self):
        optimizer=self.optimizer('s=p.read_text()\np.unlink()\nsys.stdout.write(s)',
                                 'unlinking-identity')
        cases=[self.numeric_case,ev.make_cases()[0]]
        report=ev.evaluate(optimizer,cases=cases,artifact_root=self.folder/'failures')
        self.assertEqual(report['cases'],2)
        self.assertEqual(report['executions'],sum(len(c.datasets) for c in cases))

    def test_atomic_readonly_wrong_rewrite_retains_pristine_failure_fixture(self):
        optimizer=self.optimizer("s=p.read_text().replace('DIV b,a,3','DIV b,a,2')\n"
                                 "replacement=p.with_suffix('.replacement')\n"
                                 'replacement.write_text(s)\nreplacement.chmod(0o400)\n'
                                 'replacement.replace(p)\nsys.stdout.write(s)',
                                 'atomic-readonly-wrong')
        artifacts=self.folder/'failures'
        with self.assertRaises(ev.Defect):
            ev.evaluate(optimizer,cases=[self.numeric_case],artifact_root=artifacts)
        witnesses=list(artifacts.iterdir())
        self.assertEqual(len(witnesses),1)
        self.check_pristine_witness(witnesses[0])


if __name__=='__main__':
    unittest.main()
