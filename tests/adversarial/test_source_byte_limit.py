"""Public optimizer regressions for final UTF-8 program-byte limits."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 4 * 1024 * 1024
BODY = b'LOAD x,t.x\nHJOIN l,r,x,x\nOUT l,r\n'


def padded(body, target, glyph='x'):
    start, end = body + b';', b'\n'
    available = target - len(start) - len(end)
    unit = glyph.encode('utf-8')
    return start + unit * (available // len(unit)) + b'x' * (available % len(unit)) + end


@unittest.skipUnless((ROOT / 'bin/minivm').is_file(), 'supplied interpreter is local only')
class SourceByteLimitReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='minivm-byte-limit-')
        self.folder = Path(self.temp.name)
        self.data = self.folder / 'data.json'
        self.schema = self.folder / 'schema.json'
        self.data.write_text(json.dumps({'t': {'columns': [{'name': 'x', 'type': 'INT'}],
                                              'rows': [[1]]}}))
        schema = subprocess.run([str(ROOT / 'bin/minivm'), '--schema', str(self.data)],
                                capture_output=True, check=True, timeout=10)
        self.schema.write_bytes(schema.stdout)

    def tearDown(self):
        self.temp.cleanup()

    def optimize(self, source, mode=None):
        path = self.folder / 'original.mini'
        path.write_bytes(source)
        command = [str(ROOT / 'optimize')]
        if mode:
            command.append(mode)
        got = subprocess.run([*command, str(path), str(self.schema)],
                             capture_output=True, timeout=60)
        self.assertEqual(got.returncode, 0, got.stderr)
        return got.stdout

    def run_vm(self, source):
        path = self.folder / 'run.mini'
        path.write_bytes(source)
        got = subprocess.run([str(ROOT / 'bin/minivm'), str(path), str(self.data)],
                             capture_output=True, timeout=10)
        self.assertEqual(got.returncode, 0, got.stderr)
        result = json.loads(got.stdout)
        self.assertEqual(result['ncols'], 2)
        self.assertEqual(result['rows'], [[0, 0]])
        return result

    def test_exact_limit_expansion_falls_back_byte_identically_all_modes(self):
        source = padded(BODY, LIMIT)
        self.assertEqual(len(source), LIMIT)
        self.assertEqual(self.run_vm(source)['cycles'], 27)
        for mode in [None, '--joins-only', '--no-sorted-order']:
            with self.subTest(mode=mode):
                candidate = self.optimize(source, mode)
                self.assertEqual(candidate, source)
                self.run_vm(candidate)

    def test_candidate_exactly_at_limit_is_allowed_all_modes(self):
        source = padded(BODY, LIMIT - 1)
        expected = source.replace(b'HJOIN', b'NLJOIN', 1)
        self.assertEqual(len(expected), LIMIT)
        for mode in [None, '--joins-only', '--no-sorted-order']:
            with self.subTest(mode=mode):
                candidate = self.optimize(source, mode)
                self.assertEqual(candidate, expected)
                self.assertEqual(self.run_vm(candidate)['cycles'], 16)

    def test_utf8_limit_counts_bytes_instead_of_characters(self):
        for target in [LIMIT - 1, LIMIT]:
            source = padded(BODY, target, '🙂')
            self.assertEqual(len(source), target)
            self.assertLess(len(source.decode('utf-8')), target)
            self.run_vm(source)
            for mode in [None, '--joins-only', '--no-sorted-order']:
                with self.subTest(target=target, mode=mode):
                    candidate = self.optimize(source, mode)
                    expected = source.replace(b'HJOIN', b'NLJOIN', 1) if target < LIMIT else source
                    self.assertEqual(candidate, expected)
                    self.assertLessEqual(len(candidate), LIMIT)
                    self.run_vm(candidate)

    def test_final_guard_allows_dce_to_free_room_before_fallback(self):
        body = b'LOAD dead,t.x\n' + BODY
        source = padded(body, LIMIT, 'é')
        expected = source.replace(b'HJOIN', b'NLJOIN', 1).replace(b'LOAD dead,t.x\n', b'\n', 1)
        self.assertLess(len(expected), LIMIT)
        original = self.run_vm(source)
        for mode in [None, '--no-sorted-order']:
            with self.subTest(mode=mode):
                candidate = self.optimize(source, mode)
                self.assertEqual(candidate, expected)
                self.assertLess(self.run_vm(candidate)['cycles'], original['cycles'])

    def test_normal_small_program_still_uses_cheaper_join(self):
        candidate = self.optimize(BODY)
        self.assertEqual(candidate, BODY.replace(b'HJOIN', b'NLJOIN', 1))
        self.assertLess(self.run_vm(candidate)['cycles'], self.run_vm(BODY)['cycles'])


if __name__ == '__main__':
    unittest.main()
