"""External optimizer mutations must not change the pristine VM oracle."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import evaluator  # noqa: E402


@unittest.skipUnless((ROOT / 'bin/minivm').is_file(), 'supplied interpreter is local only')
class OracleInputMutationReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minivm-oracle-review-')
        self.folder = Path(self.temp.name)
        columns = [{'name': 'n', 'type': 'NUM'}]
        self.case = evaluator.Case(
            'review-oracle-mutation',
            'LOAD n,t.n\nADD a,n,0.00\nDIV b,a,3\nOUT n,a,b\n',
            ('NUM', 'NUM', 'NUM'), False,
            [{'t': {'columns': columns, 'rows': [['6.00'], ['9'], [None]]}},
             {'t': {'columns': columns, 'rows': [['12.00']]}}])

    def tearDown(self):
        self.temp.cleanup()

    def optimizer(self, mutation, emission):
        path = self.folder / 'optimizer'
        path.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nimport sys\n'
                        'p=Path(sys.argv[1])\ns=p.read_text()\n'
                        'bad=s.replace("DIV b,a,3","DIV b,a,2")\n'+
                        mutation+'\nsys.stdout.write('+emission+')\n')
        path.chmod(0o755)
        return path

    def evaluate(self, optimizer):
        return evaluator.evaluate(optimizer, cases=[self.case],
                                  artifact_root=self.folder / 'failures')

    def test_inplace_wrong_rewrite_is_rejected_with_pristine_witness(self):
        optimizer = self.optimizer('p.write_text(bad)', 'bad')
        with self.assertRaises(evaluator.Defect):
            self.evaluate(optimizer)
        witnesses = list((self.folder / 'failures').glob('*/failure.json'))
        self.assertEqual(len(witnesses), 1)
        self.assertEqual((witnesses[0].parent / 'original.mini').read_text(), self.case.program)
        evidence = json.loads(witnesses[0].read_text())
        self.assertNotEqual(evidence['expected']['rows'], evidence['actual']['rows'])

    def test_equivalent_inplace_comment_rewrite_is_accepted(self):
        optimizer = self.optimizer('p.write_text(s+"; normalized in place\\n")',
                                   's+"; normalized in place\\n"')
        self.assertEqual(self.evaluate(optimizer)['executions'], 2)

    def test_corrupting_input_does_not_invalidate_correct_stdout(self):
        optimizer = self.optimizer('p.write_text(bad)', 's')
        self.assertEqual(self.evaluate(optimizer)['executions'], 2)


if __name__ == '__main__':
    unittest.main()
