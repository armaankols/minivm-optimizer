#!/usr/bin/env python3
"""Measure the fixed supplied examples through the public optimizer interface.

This small benchmark is separate from the evaluator. It checks exact results;
the implemented rules preserve numeric representations and row order.
Broader semantic comparison and adversarial cases belong to the evaluator.
"""

import argparse
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def run(command):
    start = time.monotonic()
    result = subprocess.run(command, capture_output=True, timeout=60, check=True)
    return result.stdout, time.monotonic() - start


def result_rows(value):
    return {key: value[key] for key in ("ncols", "rows")}


def join_changes(original, candidate, allow_dead=False):
    before, after = original.split(b'\n'), candidate.split(b'\n')
    if len(before) != len(after):
        raise ValueError('optimizer changed physical line count')
    changes = []
    for number, (left, right) in enumerate(zip(before, after), 1):
        if left == right:
            continue
        match = re.match(rb'[ \t]*(NLJOIN|HJOIN)(?=[ \t])', left, re.IGNORECASE)
        if not match:
            dead = re.match(rb'[ \t]*(LOAD|IOTA|SLICE|ISNULL|UPPER|RTRIM|TRIM|LEN|NULLIFE|LEFT|SUBSTR|YEAR|MONTH|DAY|DOW)(?=[ \t])', left, re.IGNORECASE)
            if allow_dead and dead:
                semi = left.find(b';')
                remaining = left[:dead.start(1)] + left[semi:] if semi >= 0 else b'\r' if left.endswith(b'\r') else b''
                if right == remaining:
                    changes.append({'line': number, 'from': dead.group(1).decode(), 'to': None})
                    continue
            raise ValueError('non-join source changed')
        new = b'HJOIN' if match.group(1).upper() == b'NLJOIN' else b'NLJOIN'
        if right != left[:match.start(1)] + new + left[match.end(1):]:
            raise ValueError('join operands or other source bytes changed')
        changes.append({'line': number, 'from': match.group(1).decode(), 'to': new.decode()})
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("optimizer", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument('--joins-only', action='store_true', help='isolate the frozen join stage')
    args = parser.parse_args()
    optimizer = args.optimizer.resolve(strict=True)
    vm = ROOT / "bin" / "minivm"
    measurements = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="minivm-benchmark-") as temporary:
        candidate_path = Path(temporary) / "candidate.mini"
        for program in sorted((ROOT / "examples" / "programs").glob("*.mini")):
            baseline_bytes, baseline_seconds = run(
                [str(vm), str(program), str(ROOT / "examples" / "data.json")]
            )
            baseline = json.loads(baseline_bytes)
            expected = json.loads(
                (ROOT / "examples" / "expected" / (program.stem + ".json")).read_text()
            )
            if baseline != expected:
                raise ValueError(f"supplied expected result differs: {program.name}")
            candidate_bytes, optimizer_seconds = run(
                [str(optimizer), *(['--joins-only'] if args.joins_only else []), str(program), str(ROOT / "examples" / "schema.json")]
            )
            if not candidate_bytes or len(candidate_bytes) > 4 * 1024 * 1024:
                raise ValueError(f"invalid candidate size: {program.name}")
            candidate_bytes.decode("utf-8", errors="strict")
            changes = join_changes(program.read_bytes(), candidate_bytes, allow_dead=not args.joins_only)
            candidate_path.write_bytes(candidate_bytes)
            candidate_json, candidate_seconds = run(
                [str(vm), str(candidate_path), str(ROOT / "examples" / "data.json")]
            )
            candidate = json.loads(candidate_json)
            if result_rows(candidate) != result_rows(baseline):
                raise ValueError(f"exact result mismatch: {program.name}")
            measurements.append(
                {
                    "program": program.name,
                    "baseline_cycles": baseline["cycles"],
                    "candidate_cycles": candidate["cycles"],
                    "cycles_saved": baseline["cycles"] - candidate["cycles"],
                    "optimizer_seconds": optimizer_seconds,
                    "baseline_vm_seconds": baseline_seconds,
                    "candidate_vm_seconds": candidate_seconds,
                    "candidate_is_byte_identical": candidate_bytes == program.read_bytes(),
                    "join_changes": [c for c in changes if c['to'] is not None],
                    "dead_removed": [c for c in changes if c['to'] is None],
                }
            )
    report = {
        "suite": "supplied-examples-v1",
        "stage": 'joins-only' if args.joins_only else 'joins-plus-dce',
        "python": platform.python_version(),
        "platform": platform.platform(),
        "measurement_policy": "one invocation per entry; process startup included; wall times are noisy",
        "benchmark_seconds": time.monotonic() - started,
        "measurements": measurements,
        "total_baseline_cycles": sum(row["baseline_cycles"] for row in measurements),
        "total_candidate_cycles": sum(row["candidate_cycles"] for row in measurements),
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
    sys.stdout.write(encoded)


if __name__ == "__main__":
    main()
