# Setup and reproducible checks

Requires Python 3.9+ and a POSIX host. All Python dependencies are standard-library
or repository modules; there is no pip install step. Verified host: macOS arm64,
Python 3.9.6. Linux is an intended POSIX target, not a completed second-platform test.
Windows subprocess management is not supported by this evaluator.

## Get the sources and interpreter

Use a full-history clone of `https://github.com/armaankols/minivm-optimizer.git`.
Avoid a shallow/source-only export: comparison tools read older optimizer text
from Git commits. The original optimization freeze is `49c7048`; review current HEAD, including
post-review correctness fixes. Confirm the actual published branch/HEAD.

The assignment's original `bin/` must be restored locally. It is intentionally
not committed or submitted. Replace the placeholder with the original bundle path:

```sh
python3 --version
cp -R /path/to/original-assignment-bundle/bin ./bin
bin/minivm examples/programs/q0001.mini examples/data.json
```

Git preserves executable bits for `optimize`, `evaluate` and the archived script.
If copying the interpreter lost its executable bits, restore those locally. Use
the supplied wrapper `bin/minivm`, not a direct native-build invocation; the wrapper
selects OS/architecture and handles the bundle's macOS quarantine behavior. If no
build runs, obtain a matching build from the assignment provider; no substitute
interpreter source is included here.

## Required interfaces and tests

```sh
./optimize examples/programs/q0001.mini examples/schema.json
./evaluate ./optimize
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
```

Original frozen baseline: public 26 cases / 70 datasets, 75 evaluator and 75 adversarial
tests. Current post-review suites contain 79 evaluator and 83 adversarial tests
(162 total). Use these two discovery roots explicitly. A clean exit is finite evidence,
not a soundness proof. Independent identity and defective optimizers are exercised
by tests and `tools/verify_baseline.py`.

## Reproduce without overwriting historical receipts

```sh
review_dir="$(mktemp -d)"
python3 tools/verify_baseline.py --output "$review_dir/cli-checks.json"
python3 tools/benchmark.py ./optimize --output "$review_dir/examples.json"
python3 tools/benchmark.py ./optimize --no-sorted-order --output "$review_dir/prior-pipeline.json"
python3 tools/benchmark_sorted.py --output "$review_dir/sorted-contribution.json"
python3 tools/benchmark_dce.py --output "$review_dir/dce-contribution.json"
python3 tools/compare_join_policies.py --output "$review_dir/join-policies.json"
python3 tools/compare_join_policies.py --holdouts-only --output "$review_dir/join-holdouts.json"
python3 tools/compare_join_policies.py --optimizer experiments/profile_optimizer.py --output "$review_dir/profile-experiment.json"
python3 tools/probe_join_scale.py --output "$review_dir/scale.json"
```

`--joins-only` runs only frozen join selection; `--no-sorted-order` runs joins+DCE;
default runs joins+sorted-order+DCE. The DCE benchmark disables sorted-order to
isolate that contribution. The sorted benchmark retains all prior 32 cases plus
seven labeled rule-focused cases. Old reports are historical snapshots and may
describe earlier active policies; current entry points are in the handoff.

Failure artifacts go to ignored `.evaluation-failures/`; logs/results written
under `$review_dir` do not alter tracked files. VM binaries stay in ignored bin/.
The default lifetime replay compares successful original/current runs; explicitly
adding `--include-unsafe` runs the old failure and may need roughly 1 GiB of memory.

Post-review regression results are in `records/post-review/RESULTS.md`.
A fresh local clone check at the original frozen commit is recorded in
`records/submission-audit/clean-checkout.json`. It uses the original local
interpreter on the same host; it does not certify network setup or other platforms.
