"""Executable VM witnesses, independent of optimizer implementation.

Run: python3 -m unittest discover -s tests/adversarial -v
"""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
VM = ROOT / "bin" / "minivm"
FIXTURES = Path(__file__).with_name("semantic_witnesses.json")


class SemanticWitnesses(unittest.TestCase):
    @unittest.skipUnless(VM.is_file(), "supplied MiniVM interpreter is local only")
    def test_documented_semantic_boundaries(self):
        for fixture in json.loads(FIXTURES.read_text()):
            with self.subTest(witness=fixture["name"]):
                with tempfile.TemporaryDirectory(prefix="minivm-adversarial-") as directory:
                    directory = Path(directory)
                    data = directory / "data.json"
                    program = directory / "program.mini"
                    data.write_text(json.dumps(fixture["data"]))
                    for variant in fixture["variants"]:
                        with self.subTest(variant=variant["name"]):
                            program.write_text(variant["program"])
                            result = subprocess.run(
                                [str(VM), str(program), str(data)],
                                capture_output=True, text=True, timeout=5,
                            )
                            self.assertEqual(result.returncode, variant["status"], result.stderr)
                            if variant["status"] == 0:
                                output = json.loads(result.stdout)
                                self.assertEqual(output["ncols"], variant["ncols"])
                                self.assertEqual(output["rows"], variant["rows"])
                            else:
                                self.assertEqual(result.stdout, "")
                                self.assertIn(variant["error"], result.stderr)


if __name__ == "__main__":
    unittest.main()
