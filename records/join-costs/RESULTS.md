# Join cost-model comparison and refinement

The exact same eight supplied examples and eleven targeted workloads were run
under the prior rule (commit 3155414), refined rule, always-HJOIN and always-NLJOIN.
Every policy is invoked as an executable; every resulting program is audited for
opcode-only changes and executed by MiniVM on identical data. Complete ordered
results and representations agree. No new semantic rewrite is included.

## Same-corpus comparison: instruction cycles

| Corpus | Prior rule | Refined rule | Always HJOIN | Always NLJOIN |
|---|---:|---:|---:|---:|
| Eight supplied examples | 60167 | 60167 | 60567 | 72953 |
| Eleven targeted workloads | 52666 | 45994 | 77396 | 376846 |
| All nineteen | 112833 | 106161 | 137963 | 449799 |

Exactly one selected case improves: the matching-statistics string skew saves
6672 cycles. Eighteen are unchanged, with no new regressions on this fixed set.
The targeted synthetic cases strongly affect aggregate totals; these results do
not establish a representative production speedup or universal best policy.

| Workload | Prior | Refined | Always H | Always NL |
|---|---:|---:|---:|---:|
| q0001 | 13570 | 13570 | 13766 | 13258 |
| q0002 | 3617 | 3617 | 3617 | 4049 |
| q0003 | 8562 | 8562 | 8562 | 13527 |
| q0004 | 18442 | 18442 | 18638 | 20894 |
| q0005 | 5518 | 5518 | 5526 | 5802 |
| q0006 | 6338 | 6338 | 6338 | 11303 |
| q0007 | 2596 | 2596 | 2596 | 2596 |
| q0008 | 1524 | 1524 | 1524 | 1524 |
| Numeric tiny | 31 | 31 | 55 | 31 |
| Numeric large | 1040 | 1040 | 1040 | 4368 |
| Numeric cost tie | 208 | 208 | 208 | 208 |
| Empty left | 48 | 48 | 240 | 48 |
| Duplicates / NULLEQ | 59 | 59 | 93 | 59 |
| Asymmetric strings | 2128 | 2128 | 33264 | 2128 |
| Larger long strings | 11516 | 11516 | 11516 | 339060 |
| Matching-statistics string skew | 28852 | 22180 | 28852 | 22180 |
| Stale large estimate / tiny actual | 48 | 48 | 48 | 28 |
| Stale tiny estimate / large actual | 4368 | 4368 | 1040 | 4368 |
| Unknown statistics / large actual | 4368 | 4368 | 1040 | 4368 |

Always-NL is better on q0001, while always-H is better on the unknown-statistics
large case. The selected rule is not best on every input. Tiny joins and long
asymmetric string keys show why always-H is also an inadequate general policy.

## Why matching statistics still gave a bad decision

Each side contains 63 empty strings and one 10000-byte string. Both reported means
are correct: 10000/64 = 156.25 bytes. The old estimate substitutes the shorter mean
for the mean of pairwise shorter lengths:

```
old pair-byte estimate = 64 * 64 * min(156.25,156.25) = 640000
actual pair-byte cost  = 1 * 1 * 10000 = 10000
```

| Pair class | Pair count | Shorter string bytes per pair |
|---|---:|---:|
| Empty / empty | 3969 | 0 |
| Empty / long, either direction | 126 | 0 |
| Long / long | 1 | 10000 |

The mean loses the frequency distribution. NLJOIN pays 10000 string-byte cycles
over all 4096 candidate pairs. HJOIN processes the long value on each input side,
paying 20000 string-byte cycles. Including per-pair/per-row overhead and the common
LOAD/OUT/output-pair costs gives NL 22180 versus H 28852. The old rule's mistake was
in its cost estimate, not result equivalence. The reviewer derived this
independently before receiving the coordinator's proposed implementation.

## Defensible cost-only refinement

Direct LOAD string profiles contain NULL mass at zero bytes, UTF-8 byte lengths
and frequencies for up to eight reported common values, and a mean bucket for
the remaining non-NULL values. Weighted pairwise min(length) replaces min(mean).
Hash byte costs use the corresponding all-row mean. Full common distributions
are exact for matching data; a residual mean does not identify tail shape.

With exact matching averages, min is concave, so replacing each residual length
distribution by its mean upper-estimates its NL byte term. Partitioning out
observed common values is therefore a principled refinement of the previous
single-mean approximation. It does not establish that a chosen hash join is
optimal; an unknown skewed tail can still make NL cheaper.

The code validates counts/common/distinct consistency and inferred byte totals.
Reported two-decimal averages imply rounding intervals; unique integer byte totals
are recovered where possible, otherwise a rounding margin keeps the original
opcode near ties. That margin does not bound unknown tail shape or stale stats.
GATHER, SLICE and value-changing operations discard profiles; FILL literals can
provide exact constant profiles. Source bytes other than join opcodes remain
unchanged. Statistics still justify no semantic assumption about runtime rows.

## Separate holdouts, including losses

These new cases do not replace or enter the nineteen-input totals above.

| Holdout | Prior | Refined | Always H | Always NL |
|---|---:|---:|---:|---:|
| NULL skew, no NULLEQ | 20914 | 14242 | 20914 | 14242 |
| NULL skew, NULLEQ | 28852 | 22180 | 28852 | 22180 |
| UTF-8 4000-byte tail | 16852 | 16180 | 16852 | 16180 |
| ASCII 1000-byte tail | 10852 | 10852 | 10852 | 13180 |
| Full common UTF-8 distribution | 268 | 268 | 268 | 272 |
| Homogeneous residual lengths | 28120 | 28120 | 28120 | 51448 |
| Truncated common / heterogeneous tail | 21358 | 21358 | 21358 | 18655 |
| Rounded mean, near tie | 11064 | 11063 | 11063 | 11064 |
| Rounded negative central residual | 81608 | 81608 | 81608 | 157629 |
| Stale profile / all short strings | 9232 | 16528 | 9232 | 16528 |

The last row is a **new 7296-cycle regression** relative to the old rule. The
schema statistics describe the seed skew, but actual data contains 64 short `x`
values per side. This holds the same declarations and constraints while changing
the length distribution. Better use of a snapshot does not guarantee a better
choice after drift. Outputs still agree exactly.

## Combined tradeoff and freeze recommendation

| Measurement set | Simple rule | Refined rule | Refined minus simple |
|---|---:|---:|---:|
| Fixed nineteen cases | 112833 | 106161 | -6672 |
| Stale-profile holdout alone | 9232 | 16528 | +7296 |
| Fixed nineteen plus that holdout | 122065 | 122689 | +624 |
| Other nine holdouts | 219888 | 205871 | -14017 |
| All ten holdouts | 229120 | 222399 | -6721 |
| All twenty-nine measured cases | 341953 | 328560 | -13393 |

The stale-profile loss is larger than the fixed-set gain: adding that case makes
the refinement 624 cycles worse. It would also be misleading to omit the other
nine holdouts: with every measured case included, the refinement saves 13393
cycles. These are unweighted diagnostic totals, not sampled workload frequencies.
The sparse-tail cases overlap in behavior; neither aggregation predicts expected
production cost or establishes dominance.

**Recommendation: freeze the simpler `3155414` policy for this assignment.**
The refined model has a principled mathematical benefit, but adds roughly100
active lines of distribution, rounding and invalidation logic; improves none of
the eight supplied examples; retains unknown-tail/derived-column limitations;
and has a concrete drift case that erases its fixed-set gain. Without a broader,
representative validation set, those benefits do not justify the added complexity
under the requested few-defensible-optimizations scope. This is an engineering
decision, not a claim that the simpler rule generally runs faster.

The active implementation has returned to the simple policy. The exact refined
source remains executable as `experiments/profile_optimizer.py`, its tests remain
active, and every prior report/holdout is preserved. No further case-specific join
tuning was performed. `tools/summarize_join_tradeoffs.py` reproduces this table
from archived `after.json` and `holdouts.json` into `combined.json`.

The truncated-common case retains a 2703-cycle regret relative to NL. Eight common
one-byte values cover half the rows, but the unlisted 32 values include one very
long string. A residual mean bucket still loses that tail shape. Separate
evaluator holdouts also retain 6672-cycle regrets after profile invalidation on
derived columns. These limitations are preserved, not removed to improve totals.

## Verification, timing and reproducibility

- Final evaluator suite: 59 tests passed in 19.026 seconds.
- Final independent adversarial suite: 41 tests passed in 8.507 seconds.
- Public evaluator: 26 cases / 70 execution pairs pass, wall 4.331 seconds,
  optimizer subprocess sum 2.156 seconds, paired VM execution 1.252 seconds.
- Optimizer-only 20k-instruction / 20k-column probe: 0.255 seconds. This is not a
  worst-case bound or a VM-equivalence benchmark.
- Original semantic, source-byte, register reassignment, NULL/precision, process,
  malformed-output and deadline regressions remain included. No new semantic
  failure was confirmed; finite tests do not prove soundness or optimality.

From the repository root:

```
python3 tools/compare_join_policies.py --reference-commit 3155414 --output records/join-costs/after.json
python3 tools/compare_join_policies.py --holdouts-only --output records/join-costs/holdouts.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
./evaluate ./optimize
```

`before.json` was captured before the optimizer change; `after.json` includes a
reference executable recovered from Git 3155414. Independent specialist snapshots
and reports are in `tests/evaluator/COST_REPORT.md` and
`tests/adversarial/COST_REVIEW.md`. Existing historical records are preserved.

New work remains local because GitHub DNS resolution still fails in this
environment; the user handles pushes under the standing authorization. All
tracked artifacts are text-only; supplied binaries stay local. Model/reasoning
configuration and unavailable usage telemetry are unchanged from SESSION.md.
