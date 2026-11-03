# Frozen join policy and conservative dead-code milestone

## Join decision

The active join model is the simpler `3155414` policy. The exact refined source
from `48ae105` is retained as `experiments/profile_optimizer.py`, with its positive
tests, counterexamples and all historical measurements. No further join tuning.

| Combined comparison | Simple | Refined | Refined minus simple |
|---|---:|---:|---:|
| Fixed nineteen cases | 112833 | 106161 | -6672 |
| Stale-profile holdout | 9232 | 16528 | +7296 |
| Those twenty cases together | 122065 | 122689 | +624 |
| All twenty-nine measured cases | 341953 | 328560 | -13393 |

Adding the stale case reverses the fixed-set gain. Including every other holdout
favors the refinement overall. Neither unweighted diagnostic collection is a
representative workload; the tail cases are related. The simpler model is an
engineering choice for the assignment's scope: roughly 100 fewer active lines,
no loss on the eight examples, fewer rounding/distribution/invalidation assumptions.
It is not claimed to be generally faster or optimal. Detailed evidence and the
reproducible aggregation are in `records/join-costs/RESULTS.md` and `combined.json`.

## Separate DCE contribution

The required two-argument CLI selects joins first, then removes proven-total dead
first definitions. `--joins-only` isolates the frozen baseline. The benchmark
asserts that the incremental DCE source differences contain only permitted dead
instruction removals, with no changed join choices.

| Example | Frozen joins only | Full pipeline | DCE savings |
|---|---:|---:|---:|
| q0001 | 13570 | 13536 | 34 |
| q0002 | 3617 | 3527 | 90 |
| q0003 | 8562 | 8562 | 0 |
| q0004 | 18442 | 18442 | 0 |
| q0005 | 5518 | 5518 | 0 |
| q0006 | 6338 | 6338 | 0 |
| q0007 | 2596 | 2444 | 152 |
| q0008 | 1524 | 1524 | 0 |
| Total | 60167 | 59891 | 276 |

Three improve, five unchanged, no regressions. DCE contributes 0.459% beyond the
frozen join stage. Against unoptimized 60363 cycles, total savings are 472 cycles
(0.782%): 196 from join selection and 276 from DCE. This does not claim to offset
the archived profile model's gain across all 29 diagnostic cases.

All eleven targeted join cases and all ten join holdouts remain in the regression
benchmark; each has zero incremental DCE change and identical exact results.
The benchmark therefore preserves all 29 prior join cases. Three new positive
cases are separately labeled, not substituted into representative totals:

| DCE-positive fixture | Joins only | Full | Saved |
|---|---:|---:|---:|
| Dead string chain | 100 | 12 | 88 |
| Dead index chain | 36 | 12 | 24 |
| Dead date parts | 68 | 12 | 56 |

`benchmark.json` records all 32 cases, individual source changes and optimizer/VM
wall times. Outputs, widths, numeric representations, associations, duplicate
multiplicity and order are checked exactly.

## Proof boundary and confirmed failure/fix

Only dead first definitions from a small whitelist may disappear: valid schema
LOAD; proven-column IOTA/SLICE/ISNULL; typed STR unary functions and validated
LEFT/SUBSTR counts; typed DATE parts. Guaranteed declarations and instruction
postconditions supply type facts. Stats never establish totality. Unknown writes
invalidate facts; unknown syntax disables the pass. Retained potentially failing
instructions retain every input dependency. FILL/GATHER/arithmetic/TRUNC/SORT/
joins/groups are not eliminated. See `docs/dce.md` for exact conditions.

During integration, the coordinator reproduced an originally successful program
failing after DCE: eight 2000-by-2000 HJOINs produce large position columns, and
apparently dead LOAD overwrites release them. Removing the overwrites leaves old
values resident and exceeds 64000000 register values. Before fix: original exit 0,
candidate exit 1. This was a successful-source soundness failure, not merely an
ambiguity about preserving an original resource error.

The fix requires **first textual definitions only**, tracking every prior write
including both join outputs and unknown-kind writes. It never relaxes after an
earlier definition is deleted. All overwrites stay. The confirmed fixture now
has original/current exit 0 with exact results and 64226104 cycles. Before/after
evidence is retained in `lifetime-*.json`; both specialists independently reviewed
the guard and added lightweight regressions without repeating the heavy probe.

## Verification and delivery

- Final evaluator-owned suite: 75 tests pass in 25.125 seconds.
- Final independent adversarial suite: 57 tests pass in 17.141 seconds.
- Total 132 passing tests, including semantic-error, lifetime, lexical, numeric,
  output, process and deadline regressions. No test/holdout was dropped.
- Public CLI accepts independent identity and the current optimizer, each
  completing 26 cases / 70 execution pairs. All five baseline mutants still reject
  with retained witnesses.
- Current optimizer public evaluation: 4.325 seconds external wall. Example
  optimizer calls are approximately 80-82 ms, including startup; the 20k-instruction/
  20k-column optimizer-only probe takes 0.336 seconds. Timings are single-run and
  noisy, not a claim of end-to-end speedup.

Commands from repository root, with supplied interpreter installed locally:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
python3 tools/benchmark_dce.py --output records/dce/benchmark.json
python3 tools/verify_baseline.py --output records/dce/cli-checks.json
python3 tools/summarize_join_tradeoffs.py
python3 tools/reproduce_dce_lifetime.py
```

The optional `--include-unsafe` lifetime replay also runs the saved failing
candidate and may use roughly 1 GiB of memory; it is not part of the default tests.
The coordinator already executed the original heavy before-fix witness and
verified the fixed result. No general proof of resource-failure equivalence for
failing originals or NL/H work accounting is claimed. Finite tests are evidence,
not soundness proofs. Narrow scope intentionally leaves substantial dead work.

Specialist logs: `tests/evaluator/DCE_REPORT.md` and
`tests/adversarial/DCE_REVIEW.md`. Git history and original artifacts are preserved;
all submission files are text, and interpreter binaries remain local. New commits
are local while GitHub is unreachable; the user handles pushes. No model overrides,
invented usage numbers, further join tuning or additional rewrite was introduced.
