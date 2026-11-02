#!/usr/bin/env python3
"""Record end-to-end public CLI acceptance/rejection, without optimizer imports."""

import argparse
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = {
    "empty_result": "LOAD x,t.x\nLOAD s,t.s\nSLICE x,x,0\nSLICE s,s,0\nOUT x,s\n",
    "drop_duplicates": "LOAD x,t.x\nLOAD s,t.s\nGROUP g,x,s\nGFIRST i,g\nGATHER x,x,i\nGATHER s,s,i\nOUT x,s\n",
    "swap_columns": "LOAD x,t.x\nLOAD s,t.s\nOUT s,x\n",
    "break_row_associations": "LOAD x,t.x\nLOAD s,t.s\nSORT i,x ASC NF\nGATHER x,x,i\nOUT x,s\n",
    "replace_null_with_zero": "LOAD x,t.x\nLOAD s,t.s\nNVL x,x,0\nOUT x,s\n",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "interface": "./evaluate OPTIMIZER",
        "checks": [],
    }
    with tempfile.TemporaryDirectory(prefix="minivm-baseline-cli-") as directory:
        directory = Path(directory)
        identity = directory / "independent_identity"
        identity.write_text("#!" + sys.executable + "\nimport sys\nsys.stdout.buffer.write(open(sys.argv[1], 'rb').read())\n")
        identity.chmod(0o755)
        commands = [("independent_identity", identity, None, 0),
                    ("current_optimizer", ROOT / "optimize", None, 0)]
        for name, source in MUTANTS.items():
            optimizer = directory / name
            # This is a deliberate defective optimizer, independent of evaluator
            # implementation. The retained source is its complete stdout program.
            optimizer.write_text("#!" + sys.executable + "\nprint(" + repr(source) + ")\n")
            optimizer.chmod(0o755)
            commands.append((name, optimizer, source, 1))
        for name, optimizer, source, expected_status in commands:
            started = time.monotonic()
            completed = subprocess.run(
                [str(ROOT / "evaluate"), str(optimizer)], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=900,
            )
            elapsed = time.monotonic() - started
            entry = {
                "name": name,
                "expected_exit": expected_status,
                "actual_exit": completed.returncode,
                "wall_seconds": elapsed,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            if source is not None:
                entry["optimizer_prints"] = source
            if completed.returncode == 1 and "; witness " in completed.stderr:
                witness = Path(completed.stderr.rsplit("; witness ", 1)[1].strip())
                retained = args.output.resolve().parent / "witnesses" / name
                shutil.copytree(witness, retained, dirs_exist_ok=True)
                entry["retained_witness"] = str(retained.relative_to(args.output.resolve().parent))
            report["checks"].append(entry)
            # Persist even an unexpected result so failures cannot disappear.
            args.output.write_text(json.dumps(report, indent=2) + "\n")
            print(f"{name}: exit {completed.returncode} (expected {expected_status}), {elapsed:.3f}s")
            if completed.returncode != expected_status:
                raise SystemExit(f"unexpected evaluator result for {name}")
            if expected_status == 1 and "witness" not in completed.stderr:
                raise SystemExit(f"missing failure witness for {name}")


if __name__ == "__main__":
    main()
