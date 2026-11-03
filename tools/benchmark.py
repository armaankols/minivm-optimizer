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


def expected_iota(line):
    text = line.decode('utf-8')
    match = re.match(r'[ \t]*(SORT)[ \t]+', text, re.IGNORECASE)
    if not match:
        return None
    operands = text[match.end():].split(';', 1)[0].split(',')
    if len(operands) < 2:
        return None
    dest, source = operands[0].strip(), operands[1].split()[0]
    if not all(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', value) for value in (dest, source)):
        return None
    tail = text.find(';')
    if tail < 0:
        tail = len(text.rstrip('\r\n'))
    while tail > match.start(1) and text[tail-1] in ' \t':
        tail -= 1
    return (text[:match.start(1)] + 'IOTA ' + dest + ', ' + source + text[tail:]).encode()


def join_changes(original, candidate, allow_dead=False, allow_sorted=False):
    before, after = original.split(b'\n'), candidate.split(b'\n')
    if len(before) != len(after):
        raise ValueError('optimizer changed physical line count')
    changes = []
    for number, (left, right) in enumerate(zip(before, after), 1):
        if left == right:
            continue
        match = re.match(rb'[ \t]*(NLJOIN|HJOIN)(?=[ \t])', left, re.IGNORECASE)
        if not match:
            iota = expected_iota(left) if allow_sorted else None
            if iota is not None and right == iota:
                changes.append({'line': number, 'from': 'SORT', 'to': 'IOTA'})
                continue
            names = 'LOAD|IOTA|SLICE|ISNULL|UPPER|RTRIM|TRIM|LEN|NULLIFE|LEFT|SUBSTR|YEAR|MONTH|DAY|DOW'
            dead = re.match(rb'[ \t]*('+names.encode()+(b'|SORT' if iota is not None else b'')+rb')(?=[ \t])', left, re.IGNORECASE)
            if allow_dead and dead:
                semi = left.find(b';')
                remaining = left[:dead.start(1)] + left[semi:] if semi >= 0 else b'\r' if left.endswith(b'\r') else b''
                if right == remaining:
                    event = {'line': number, 'from': dead.group(1).decode(), 'to': None}
                    if iota is not None:
                        event['via'] = 'IOTA'
                    changes.append(event)
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
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--joins-only', action='store_true', help='isolate the frozen join stage')
    mode.add_argument('--no-sorted-order', action='store_true', help='isolate prior joins plus DCE')
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
                [str(optimizer), *(['--joins-only'] if args.joins_only else ['--no-sorted-order'] if args.no_sorted_order else []), str(program), str(ROOT / "examples" / "schema.json")]
            )
            if not candidate_bytes or len(candidate_bytes) > 4 * 1024 * 1024:
                raise ValueError(f"invalid candidate size: {program.name}")
            candidate_bytes.decode("utf-8", errors="strict")
            changes = join_changes(program.read_bytes(), candidate_bytes, allow_dead=not args.joins_only,
                                   allow_sorted=not args.joins_only and not args.no_sorted_order)
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
                    "join_changes": [c for c in changes if c['from'].upper() in ('NLJOIN', 'HJOIN')],
                    "sort_changes": [c for c in changes if c['from'].upper() == 'SORT'],
                    "dead_removed": [c for c in changes if c['to'] is None],
                }
            )
    report = {
        "suite": "supplied-examples-v1",
        "stage": 'joins-only' if args.joins_only else 'joins-plus-dce' if args.no_sorted_order else 'joins-sort-dce',
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
