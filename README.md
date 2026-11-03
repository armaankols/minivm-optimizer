# **2.06% FEWER MINIVM INSTRUCTION CYCLES**

**60,363 → 59,121 cycles across the eight supplied examples: 1,242 cycles saved.**
Three examples improved; five were unchanged. This measures VM work, not elapsed-time speedup.

## Assignment and approach

We built a tool to make MiniVM programs do less work without changing their answers,
plus an independent checker to catch incorrect optimizations.

MiniVM operates on columns of values held in named registers. Its **instruction
cycles** measure the work its instructions perform. The assignment required an
optimizer finishing within 60 seconds and an evaluator finishing within 15 minutes.
Results must agree on every dataset satisfying the declared constraints, preserving
required ordering and numeric values within `1e-6` relative error.

The final implementation, `b95985d`, has three stages: join algorithm selection,
reuse of guaranteed stored order, and restricted removal of unused computations.
One coordinator owned optimizer/integration/Git, one specialist owned the evaluator,
and one independently reviewed semantics and counterexamples.

A central distinction guided every decision: schema **constraints** are guarantees;
**statistics** describe a sample and may become stale. Statistics choose between
already equivalent operations; they never justify discarding results or errors.
See the [assignment](docs/assignment.md) and [comparison contract](records/CONTRACT.md).

### Takeaway

Correctness came from documented guarantees and explicit preconditions. Statistics
helped predict cost, with no promise of improvement on every input.

## Baseline and evaluator

We established that the checker could recognize wrong answers before attempting
any speed improvements.

Commits `b8e7f8a` and `be3395a` preserved the text starter and identity baseline,
which returns its input unchanged. All eight examples matched their supplied
expected results, totaling **60,363 cycles before and after**.

Commits `0a91af9` and `9a06eab` introduced the independent evaluator and retained
witnesses. It executes original and candidate programs in MiniVM across **26 cases
and 70 execution pairs**, using fixed seeds and alternate constraint-valid data
under one frozen schema. It preserves complete rows, duplicate counts and required
order. Numeric comparison uses decimal arithmetic and complete row matching,
avoiding a greedy pairing that could miss a valid approximate match.

The evaluator accepted identity and rejected five deliberately wrong optimizers:
empty results, dropped duplicates, swapped columns, broken row associations and
NULL replaced with zero. NULL represents missing data.

Review also corrected the checker: overly strict ordering annotations, an uncaught
decimal overflow, rejection of equivalent `1`/`"1.0"` representations, and rejection
of harmless stderr diagnostics (`11df850`). Early VM counterexamples ruled out
casual algebraic rewrites: unused division can still fail, numeric cancellation
can hide overflow, and keeping only the top sorted rows can suppress type errors.

Evidence: [baseline results](records/MILESTONE_1.md),
[evaluator history](tests/evaluator/REPORT.md),
[semantic counterexamples](tests/adversarial/semantic_witnesses.json).

### Takeaway

The evaluator needed adversarial testing too. Passing an identity optimizer alone
would not establish that it could detect defects or accept valid alternatives.

## Join selection

A join finds matching rows. We changed how those matches are found while preserving
the matches, their order and the instruction's operands.

Commit `3155414` selects between `NLJOIN` (compare row pairs) and `HJOIN` (organize
keys for lookup). The [VM specification](docs/instructions/joins.md) guarantees the
same ordered pairs and semantic errors. All operands and flags remain intact,
including `NULLEQ`, which permits missing keys to match.

For non-string keys, the model compares estimated work `L*R` against `6*(L+R)`;
strings add estimated byte costs. Unknown costs and ties retain the original
algorithm. Joins alone saved **196 cycles** across the supplied examples, improving
one and leaving seven unchanged. Tests covered duplicates, NULLs, empty inputs,
numeric precision, errors and register reassignment.

The targeted cases also exposed three performance regressions, retained today:

| Workload | Original cycles | Selected cycles | Extra cycles |
|---|---:|---:|---:|
| Skewed strings, matching statistics | 22,180 (NL) | 28,852 (H) | 6,672 |
| Estimated large, actually tiny | 28 (NL) | 48 (H) | 20 |
| Estimated tiny, actually large | 1,040 (H) | 4,368 (NL) | 3,328 |

Review found a parser bug as well: Python's broad line splitting could expose text
inside a valid string as an instruction. Splitting only at MiniVM's LF line
boundaries fixed it; nine separator variants remain tested.
[Results and limitations](records/join-selection/RESULTS.md) distinguish prediction
losses from correctness failures.

### Takeaway

Choosing between equivalent algorithms is a small, defensible optimization, but
correct selection logic can still make a poor performance prediction.

## Refined cost model: explored, then set aside

We investigated why accurate averages still produced a bad join decision, then
checked whether a more detailed model earned its complexity.

In the skewed case, each side contains 63 empty strings and one 10,000-byte string.
The correct average is 156.25 bytes. Yet using the shorter average for every pair
predicts **640,000 string-byte cycles**, while only the long/long pair contributes:
**10,000**. Averages discard the distribution needed to estimate pairwise cost.

Commit `48ae105` added common-value length profiles, an average bucket for remaining values,
rounding handling and profile invalidation after transformations. On the same fixed
19 cases, simple/refined/always-H/always-NL policies used **112,833 / 106,161 /
137,963 / 449,799 cycles** respectively. The refinement saved 6,672 on the skew
case; the other 18 were unchanged, including all eight supplied examples.

Separate **holdouts**, additional validation workloads, exposed a stale-profile
loss of 7,296 cycles—larger than that fixed-set gain:

| Join-only comparison | Simple | Refined | Refined minus simple |
|---|---:|---:|---:|
| Fixed 19 | 112,833 | 106,161 | −6,672 |
| Stale-profile holdout | 9,232 | 16,528 | +7,296 |
| Those 20 together | 122,065 | 122,689 | +624 |
| All 29 measured cases | 341,953 | 328,560 | −13,393 |

Both conclusions matter: the selected holdout reverses the fixed-set gain, while
all cases together favor the refinement. Neither unweighted diagnostic collection
represents real workload frequencies. Unknown tails remain problematic, and no
policy wins every input.

Commit `0990017` restored the simpler model: roughly 100 fewer active lines,
no loss on the supplied examples and fewer distribution/rounding assumptions.
The [exact experiment](experiments/README.md), its tests, and the
[full policy comparison](records/join-costs/RESULTS.md) remain preserved.

### Takeaway

The refinement was principled but insufficiently validated for its added complexity.
Keeping the simple rule was a scope decision, not a claim that it is generally faster.

## Dead-code elimination

Unused work can still raise errors or release memory. Deleting it safely required
more than checking whether its answer appears in the output.

Commit `0990017` added [dead-code elimination](docs/dce.md), or DCE. Backward
**liveness analysis** identifies values later instructions need. Removal additionally
requires a narrow whitelist of operations proved unable to fail under established
type and input conditions. Arithmetic, unchecked gathers, joins and other potentially
failing instructions stay, along with their dependencies.

The initial approach exposed a memory-lifetime bug. Eight 2,000-by-2,000 joins
produced large columns; apparently unused overwrites released those columns.
Deleting the overwrites kept old values alive until the candidate exceeded the
VM's **64-million-value limit**, although the original succeeded.

The fix removes only a register's **first textual definition**, counting every
prior write even if later deleted. All overwrites remain. The retained witness
now succeeds for original/current with identical results and 64,226,104 cycles.
Both specialists checked the guard and added lightweight regressions.

Against **simple joins only**, DCE saved **276 example cycles**. All 29 existing
join cases stayed in the benchmark, alongside three new positive cases. Targeted
joins and holdouts had no incremental DCE change.
[Results](records/dce/RESULTS.md) and the
[lifetime witness](records/dce/lifetime-before-fix.json) preserve the failure and fix.

### Takeaway

Register writes affect memory lifetime even when their values are unused. We kept
the conservative restriction rather than expanding deletion without that analysis.

## Guaranteed sorted order

Sorting data already guaranteed to have the required order wastes work. This stage
used a declaration that holds for every valid dataset, not an observed pattern.

Commit `49c7048` replaces eligible `SORT` instructions with `IOTA`, which generates
positions `0,1,...,N-1`. It requires current direct loads from one table, an exact
leading prefix of guaranteed sorted columns, ascending order and NULLs first.
Stable sorting preserves tied rows, so these positions are identical. The same
destination write remains, preserving register lifetime.

Derived keys, sorted suffixes, mixed tables, descending order and statistical
sortedness do not qualify. Against **joins plus DCE with this rule disabled**, the
stage saved **770 cycles** in q0001; seven examples were unchanged. Savings include
DCE newly enabled by the replacement. The expanded 39-case corpus had six
improvements and 33 unchanged cases versus that preceding pipeline, retaining all
join holdouts and their existing losses.

Review found Python/MiniVM differences in control-character whitespace and Unicode
case conversion that could suppress source errors. Seven failures were reproduced
before tightening the shared scanner. Quoted data and valid whitespace remain
supported. The reviewer checked the fix; the evaluator independently reran the
reviewer's fixtures rather than authoring a separate SORT fixture set.
[Proof and results](records/sorted-order/RESULTS.md) and the
[review log](records/sorted-order/REVIEW_LOG.md) retain that distinction.

### Takeaway

Guaranteed order delivered the largest incremental example saving. Narrow
preconditions and parser fidelity were essential to making the replacement safe.

## Independent review and fixes

A fresh reviewer found two failures that the existing passing suite had missed.
Both were reproduced before fixing, then retained as regressions.

The [review of `49c7048`](records/post-review/supplied-REVIEW.md) led to:

- **File-size preservation (`af12e15`).** Expanding `HJOIN` to `NLJOIN` added one
  byte to a valid program at the 4 MiB limit, making it fail. A final UTF-8 byte-size
  check now returns original source if the completed candidate exceeds the limit.
  Five tests cover boundaries, multibyte text, all modes and later DCE freeing room.
- **Pristine evaluator baseline (`b95985d`).** An optimizer editing its input file
  could make wrong output compare with itself, or correct output fail comparison.
  Each invocation now receives a separate input copy; the baseline is created from
  pristine in-memory source afterward. Seven mutation tests cover wrong and correct
  output, replacement/deletion and replayable failure fixtures.

The reviewer signed off on both fixes. Both supplied wrong optimizers now reject;
correct in-place controls pass. No new optimization was added.
[Before/after evidence](records/post-review/RESULTS.md) preserves the reproductions.

### Takeaway

Instruction equivalence alone does not cover file limits, and an evaluator's
expected answer must remain independent of mutations by the optimizer.

## Final results and verification

The review fixes corrected failures without changing measured cycle savings.
Performance and correctness have separate evidence and explicitly named baselines.

| Eight-example stage | Cycles | Saving versus preceding stage |
|---|---:|---:|
| Original / identity | 60,363 | 0 |
| Simple joins | 60,167 | 196 |
| Joins + DCE | 59,891 | 276 |
| Final joins + stored order + DCE | **59,121** | **770** |

The archived refined model is absent from this final pipeline. Against original
programs, three examples improve and five stay unchanged; total saving is
**1,242 cycles (2.06%)**. [Per-program measurements](records/post-review/examples.json)
include unchanged cases and separate optimizer/VM timings.

Final recorded verification passed **79 evaluator + 83 adversarial = 162 tests**.
The public evaluator completed **26 cases / 70 execution pairs**; identity/current
were accepted, all five baseline mutants were rejected, and all **39 exact-output
benchmark cases** passed. Tests cover output associations, duplicates, ordering,
numeric tolerance, malformed output, subprocess failures and deadlines.

Recorded optimizer calls took roughly **85–89 ms per example**; the public evaluator
took **5.967 seconds internally**. Startup and concurrent checks make these noisy
observations, not evidence of elapsed-time speedup.
[Full verification receipts](records/post-review/RESULTS.md) retain the logs.

### Takeaway

We demonstrated a modest cycle reduction on the supplied examples and stronger
correctness evidence, while preserving the known join-performance regressions.

## Limitations, AI use and remaining work

The final scope favors a few explainable transformations over broad coverage.
Passing tests strengthen the evidence but cannot prove correctness for all programs.

Remaining limits include stale join statistics and unknown string tails; ambiguous
assignment rules for ordering, relative-error calculation and resource failures;
incomplete VM type tags; finite data-generation coverage; and one verified macOS
host. The evaluator's **10-second VM timeout** is its own policy and could reject a
valid slow candidate; no such witness was reproduced. DCE intentionally retains
many unused operations. Broader algebraic rewrites, partial sorting and repeated-expression reuse
remain deferred because errors, register versions and resource lifetimes matter.

The recorded runtime identified Codex as based on the **GPT-6 family**, not an
authoritative exact model ID. Exact model/reasoning settings and approximate tokens
or spend remain **pending user/account information**; no estimates are invented.
[AI_USAGE.md](AI_USAGE.md), [prompts](records/PROMPTS.md) and
[development records](records/SESSION.md) preserve available information. Logs are
curated, not a complete provider conversation export.

Git retains the starter and verified milestones; binaries remain excluded. The
user confirmed earlier pushes, but latest publication is unverified because the
recorded remote check failed GitHub DNS. The [submission checklist](SUBMISSION_CHECKLIST.md)
flags publication confirmation, missing AI metadata and any available full export.

With more time and compute, we would generate programs and datasets automatically,
shrink failures to small examples, challenge the evaluator with more faulty
optimizers, exhaustively check small inputs and analyze resource lifetimes.
Broader, fixed holdouts should precede a more complex cost model or additional rewrites.

### Takeaway

The next investment should strengthen evidence and analysis before expanding scope.
Submission metadata and publication still require confirmation.
