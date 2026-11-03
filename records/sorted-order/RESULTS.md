# Guaranteed stored-order optimization

The only new optimization is SORT->IOTA for current direct LOAD keys from one
table, matching an exact nonempty leading prefix of guaranteed `sorted`, all
ASC NF. The simple join policy is unchanged. The pipeline is joins -> stored-order
elimination -> guarded DCE. No identity-GATHER or other rewrite is included.

## Isolated example contribution

Both modes run the same join selection and DCE; `--no-sorted-order` disables only
the new pass. Source audits reject changed join choices during this comparison.

| Example | Without new rule | Full pipeline | Additional savings |
|---|---:|---:|---:|
| q0001 | 13536 | 12766 | 770 |
| q0002 | 3527 | 3527 | 0 |
| q0003 | 8562 | 8562 | 0 |
| q0004 | 18442 | 18442 | 0 |
| q0005 | 5518 | 5518 | 0 |
| q0006 | 6338 | 6338 | 0 |
| q0007 | 2444 | 2444 | 0 |
| q0008 | 1524 | 1524 | 0 |
| Total | 59891 | 59121 | 770 |

One improves, seven unchanged, no regressions. The additional reduction is 1.29%
over the prior pipeline. Against unoptimized 60363 cycles, total savings are 1242
(2.06%):196 join selection +276 DCE +770 stored-order elimination. Exact results,
numeric representations, output structure, row associations, multiplicity and
order agree. q0001 line 9 becomes `IOTA r 7, r 1`, preserving its comment.

## All earlier regression workloads retained

The benchmark includes all prior 32 cases: eight examples, eleven targeted join
cases, ten join holdouts and three DCE-positive cases. Their baseline cycles
match the prior DCE record. Only q0001 changes. Every earlier join holdout stays
unchanged, including known cost-model losses; none is excluded from the report.

Seven separately labeled rule-focused cases extend that corpus to 39:

| New diagnostic case | Without rule | Full | Saved |
|---|---:|---:|---:|
| Full prefix | 80 | 44 | 36 |
| Shorter leading prefix | 64 | 44 | 20 |
| Destination aliases key | 80 | 44 | 36 |
| Dead first-definition sort | 70 | 14 | 56 |
| Suffix, rejected | 68 | 68 | 0 |
| Empty prefix input | 24 | 20 | 4 |
| Sorted sample but no guarantee, rejected | 80 | 80 | 0 |

These cases include NULLs, NUM scale-equal ties and string payloads. Some savings
include subsequent DCE of a now-unused first-definition key LOAD or IOTA; those
interactions are listed in the source-change events, not attributed solely to
the physical sort instruction. Empty SORT/IOTA themselves have equal base cost.
On the 39-case diagnostic corpus: six improve,33 unchanged,zero regressions.
No weighted production-performance claim is made from these synthetic cases.

## Correctness and confirmed parser failures

Stored ASC NF order plus stable SORT implies identity positions for every leading
prefix. Guaranteed stored types and same-table columns prevent type/length errors
at the replaced sort. The same destination write and INT result length remain;
origins are read before any aliased write and invalidated afterward. DCE still
retains overwrites that release old values. Exact preconditions are in
`docs/sorted-order.md`.

Independent reviewer probes found two classes of error suppression before the fix:
Python splits/strips FS/GS/RS/US but MiniVM rejects them, and Python Unicode case
folding converts invalid token lookalikes such as AſC or t.K into valid proof keys.
The SORT variants could turn invalid sources into successful IOTA programs. The
dead-LOAD form also exposed a preexisting DCE parsing issue.

Coordinator reproduced seven failures before editing the scanner. The scanner
now rejects those controls and non-ASCII non-whitespace characters outside quoted
strings/comments. It preserves them as literal/comment data, and permits valid
VM Unicode whitespace. All seven recorded sources now preserve exit 1 and source
bytes. A broader 29-codepoint Python-whitespace probe preserved every VM outcome.
Before/after witnesses are retained in parser-failures-*.json; literal-control
regressions from earlier milestones remain included.

## Verification and independent review

- Coordinator full evaluator suite:75 tests passed in 25.251 seconds.
- Coordinator full adversarial suite:75 tests passed in 23.493 seconds.
- Total 150 passing tests, including 16 focused sorted-order test methods and the
  two new malformed-LOAD methods. No existing tests or holdouts were removed.
- Reviewer independently derived the proof, inspected the candidate, found the
  parser failures, inspected the fix and reran all 16 methods: pass in 5.745 seconds.
- Evaluator independently reran those same reviewer fixtures:16 passed in 6.194
  seconds; public evaluator passed 26 cases/70 executions in 4.643 seconds. These
  runs overlapped; timings are observations, not isolated performance estimates.
- The evaluator's planned additional SORT fixture file was not written: both
  specialists temporarily hit usage limits, then resumed for narrow final checks.
  Independent fixture authorship and independent reruns are not conflated.
- Coordinator public CLI check accepted identity and current optimizer across
  26 cases/70 executions, and rejected all five baseline mutants with saved witnesses.
- The prior memory-lifetime reproducer still succeeds for original/current with
  exactly 64226104 cycles. It did not rerun the optional unsafe 1 GiB variant.

Coordinator current-optimizer public wall time:4.392 seconds. Example optimizer
calls: about 89-91 ms including startup. The 20k-instruction/20k-column optimizer-only
probe takes 0.445 seconds. Timings are single-run and noisy; instruction-cycle
savings do not establish an end-to-end wall-time improvement.

## Reproduction and remaining limits

```
python3 tools/benchmark_sorted.py --output records/sorted-order/benchmark.json
python3 tools/benchmark.py ./optimize --output records/sorted-order/examples-full.json
python3 tools/benchmark.py ./optimize --no-sorted-order --output records/sorted-order/examples-baseline.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
python3 tools/verify_baseline.py --output records/sorted-order/cli-checks.json
python3 tools/reproduce_dce_lifetime.py
```

Benchmarks contain raw cycles/timing and source events. Specialist evidence is
in `tests/adversarial/SORT_REVIEW.md` and `REVIEW_LOG.md` here. Source proofs are
deliberately narrow; derived orders, suffixes, DESC/NL and stronger uniqueness
reasoning are deferred. The join policy retains its known cost/limit caveats.
Finite tests provide evidence, not a universal soundness or resource-error proof.

This completes the last approved optimization before final review. Binary files
remain excluded. New commits are local while GitHub is unreachable; the user
handles pushes. Model settings/usage availability remain unchanged; no usage
counts or spend are invented.
