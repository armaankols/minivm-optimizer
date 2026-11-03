# MiniVM optimizer: project report

This assignment asked us to make existing programs run with less work while
keeping their results unchanged, and to build a separate tool that could catch
incorrect optimizers. MiniVM is a small **column virtual machine**: its registers
(named temporary storage) hold columns of values, and instructions transform
those columns. Its reported **instruction cycles** measure VM work, not elapsed
time or processor clock cycles.

We built `./optimize`, an optimizer with three deliberately narrow stages, and
`./evaluate`, an independent checker that executes original and optimized
programs. The final optimizer selects a join algorithm, avoids sorting data whose
order is guaranteed, and removes a restricted set of unused computations.
Across the eight supplied examples, cycles fell from **60,363 to 59,121**:
**1,242 cycles saved, or 2.06%**. Three examples improved and five were unchanged.
This is a measured result on those examples, not a general speedup guarantee.

The final recorded verification passed **162 tests** and **39 diagnostic benchmark
cases**. The public evaluator accepted the identity optimizer (which simply
returns its input) and our optimizer, and rejected deliberately incorrect ones.
Known join-selection regressions remain visible below. Tests provide correctness
evidence; cycle counts provide performance evidence. Neither proves universal
correctness or optimal performance.

The implementation described here is **`b95985d`**, including the independent-review
fixes. New optimizations were frozen at `49c7048`; subsequent implementation
changes fixed confirmed bugs. This README revision changes documentation only.
For a shorter entry point, see the [reviewer handoff](REVIEW_HANDOFF.md).

Navigation: [setup and run](#setup-and-run) · [development account](#baseline-and-evaluator)
· [final verification](#final-verification-and-results) ·
[limitations and submission](#limitations-and-submission) · [AI use](#ai-use-and-further-work).

## Setup and run

The Python code needs no third-party packages, but running the checks requires
the original MiniVM interpreter supplied with the assignment. Interpreter
binaries are intentionally excluded from Git and the submission.

Use Python 3.9+ on a POSIX system. The verified host was macOS arm64 with Python
3.9.6; Linux is an intended target, not a completed second-platform verification.
Windows process management is unsupported. Use a full-history checkout because
some comparison tools recover earlier optimizer versions from Git. The working
branch is `codex/baseline`; confirm the published branch includes `b95985d`.

From the repository root, restore the original interpreter bundle if `bin/` is
absent. Replace the placeholder path with the actual assignment bundle location:

```sh
python3 --version
cp -R /path/to/original-assignment-bundle/bin ./bin
bin/minivm examples/programs/q0001.mini examples/data.json
```

Use the supplied `bin/minivm` wrapper, which selects the appropriate build.
Then run the required interfaces:

```sh
./optimize examples/programs/q0001.mini examples/schema.json
./evaluate ./optimize
```

The first command prints optimized source to stdout; it does not execute it.
The second prints a JSON summary and exits 0 when its finite suite finds no
defect. Exit 1 reports a witnessed optimizer defect; exit 2 reports usage,
infrastructure trouble or incomplete evaluation. Reproductions are saved under
ignored `.evaluation-failures/`.

Run the two test suites explicitly:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
```

Use fresh output paths to preserve the historical receipts:

```sh
review_dir="$(mktemp -d)"
python3 tools/verify_baseline.py --output "$review_dir/cli-checks.json"
python3 tools/benchmark.py ./optimize --output "$review_dir/examples.json"
python3 tools/benchmark_dce.py --output "$review_dir/dce.json"
python3 tools/benchmark_sorted.py --output "$review_dir/sorted.json"
```

`--joins-only` runs just join selection. `--no-sorted-order` runs joins and
unused-computation removal. The default runs joins, stored-order optimization,
then unused-computation removal. [SETUP.md](SETUP.md) includes further comparison
and replay commands. Historical reports describe the code at their milestone;
rerunning their commands with today's optimizer does not recreate old code.

## The contract and working method

We first separated what the data promises from what merely looked likely in one
sample. That distinction determines which changes can be safe and which can
only be performance guesses.

The [assignment requirements](docs/assignment.md) specify
`./optimize PROGRAM SCHEMA`, producing equivalent source within 60 seconds, and
`./evaluate OPTIMIZER`, finishing within 15 minutes. Results must agree on **any**
data satisfying the schema's declarations and constraints. Order matters when
the input program specifies it; numeric values must agree within `1e-6` relative
error. The supplied PDF remains outside Git under the no-binary requirement;
its hash is recorded in the transcript. Original interpreter documentation starts
at [docs/README.md](docs/README.md); no interpreter source was supplied.

A **schema** describes tables and columns. Its `key`, `not_null`, `refs`, `check`
and `sorted` declarations are guarantees, with their precise meanings in
[the VM's schema documentation](docs/running.md#constraints). For example,
`check` bounds apply only to non-NULL values; NULL represents missing data.
Every field under `stats`, including row counts, distinct counts, common values
and average string lengths, describes one dataset. Those fields may be stale
when the optimized program runs. We use statistics to choose between operations
already known to be equivalent, never to prove values, types or ordering away.

The team had one coordinator owning optimizer code, integration, records and Git;
one specialist owning evaluator code/tests; and one independent adversarial
reviewer owning counterexamples and review fixtures. Shared optimizer helpers
remained coordinator-owned. There was no nested delegation. Decisions were
checked against documentation and executable VM witnesses rather than ordinary
SQL or arithmetic intuition. The [contract](records/CONTRACT.md),
[prompts and assignments](records/PROMPTS.md), [session record](records/SESSION.md)
and specialist reports preserve the available reasoning and evidence.

## Baseline and evaluator

Before trying to make programs faster, we needed a checker that could recognize
both correct and incorrect answers. Otherwise a fast wrong program could appear
to be an improvement.

Commits `b8e7f8a` and `be3395a` captured the untouched text starter and a
reproducible identity baseline. The 34 original text files are checksummed in
[STARTER.sha256](STARTER.sha256). All eight supplied programs matched their
expected VM results, including cycles; identity optimization left the total at
**60,363 → 60,363**. Binaries were preserved locally and excluded from Git.

Commit `0a91af9` implemented [evaluator.py](evaluator.py); `9a06eab` retained
verified results and witnesses. The evaluator imports no optimizer code. Its
**oracle**, meaning the source of expected answers, is execution of the original
program in MiniVM. It invokes an arbitrary optimizer executable through the
required command interface, freezes one schema, and executes the resulting
program on multiple datasets with matching declarations but varying statistics.
MiniVM validates each dataset's constraints. The public corpus contains 26 cases
and 70 original/candidate execution pairs, using seeds `1729` and `8675309`,
operator fixtures and all eight supplied examples on original and empty data.

Comparison preserves output width, complete row associations and **duplicate
multiplicity**—how many times each row appears. Ordered cases compare rows by
position. Unordered cases match whole rows; comparing columns independently
would miss values attached to the wrong row. Approximate numeric matching uses
maximum bipartite matching: it searches for a complete pairing of compatible
rows instead of greedily consuming a match that another row needs. Strings and
dates are exact, Boolean values stay distinct from integers, and known fixture
types guide interpretation of ambiguous JSON encodings.

Numeric comparison uses decimal arithmetic and the documented interpretation
`abs(a-b) <= 1e-6 * max(abs(a), abs(b))`; zero has no absolute-error allowance.
The assignment does not choose that denominator explicitly. A successful
comparison ignores cycle differences. Processes have a 60-second optimizer cap,
a 10-second per-VM-call cap, bounded output capture, descendant cleanup and an
840-second overall budget, leaving reserve below the 900-second requirement.
Deadline exhaustion is incomplete evaluation, never a clean pass.

Baseline checks accepted identity and rejected five **mutants**, intentionally
wrong optimizers: empty results, lost duplicates, swapped columns, broken row
associations and NULL replaced with zero. All retained witnesses were replayed.
The historical baseline finished with **30 evaluator tests and 17 adversarial
tests** passing. These are milestone counts, not the final 162.

Review also found problems in the checker itself. Two fixtures initially required
ordering more strictly than the assignment justified; they were corrected. An
extreme numeric-looking string caused a decimal overflow and escaped without a
witness; numeric grammar, length bounds and exception handling fixed it. An
initially strict integer parser then falsely rejected numerically equal decimal
representations such as `1` and `"1.0"`; integer and decimal slots now share the
numeric tolerance policy. Later, a correct optimizer's noisy stderr was falsely
rejected; commit `11df850` retained a bounded diagnostic prefix while draining
excess stderr. Stdout floods still fail.

These failures established that the evaluator also needed adversarial testing.
Early VM witnesses showed why broad rewrites were deferred: dead division may
still raise an error; replacing SORT followed by SLICE with TOPK can skip a type
error in discarded rows; reusing a register after reassignment can read the wrong
value; and numeric cancellation can hide intermediate overflow. We therefore
started optimization with a documented equivalence, rather than a broad algebraic
rewrite. See [baseline results](records/MILESTONE_1.md),
[evaluator history](tests/evaluator/REPORT.md), and
[semantic witnesses](tests/adversarial/semantic_witnesses.json).

## Join selection

A join finds matching rows in two columns. We tried to save work by choosing how
to find those matches, while leaving the matches themselves untouched.

Commit `3155414` added [optimizer.py](optimizer.py). `NLJOIN`, a nested-loop join,
compares row pairs. `HJOIN`, a hash join, organizes keys for lookup. The
[join specification](docs/instructions/joins.md) explicitly promises identical
pairs, duplicate multiplicity, left-then-right position order and semantic
errors. The optimizer changes only the opcode, preserving both destinations,
inputs and the `NULLEQ` flag, which allows missing keys to match. Destination/input
aliases—two operand names referring to the same register—are handled using the
input facts before recording writes.

For non-string keys, estimated work excluding common costs is `L*R` for nested
loops versus `6*(L+R)` for hashing, where L and R are input lengths. Strings add
byte-processing costs. The simple rule approximates pairwise string work using
the shorter average key length. It tracks estimates through selected operations;
unknown costs and exact cost ties keep the existing opcode. These are cost
heuristics, not facts about future data.

Against the original eight examples, joins alone reduced **60,363 → 60,167**:
196 cycles saved in q0001, seven examples unchanged. Historical verification
passed **46 evaluator and 31 adversarial tests**, covering missing values,
duplicates, numeric precision, empty inputs, errors and register reassignment.
Independent expected join pairs came from VM execution and a separate
Cartesian-pair enumeration, not optimizer internals.

The eleven targeted workloads exposed the limits immediately: six improved,
two were unchanged and three regressed. These losses remain in the final corpus:

| Targeted workload | Original algorithm and cycles | Simple rule and cycles | Change |
|---|---:|---:|---:|
| Matching-statistics skewed strings | NLJOIN: 22,180 | HJOIN: 28,852 | +6,672 |
| Estimated large, actually tiny | NLJOIN: 28 | HJOIN: 48 | +20 |
| Estimated tiny, actually large | HJOIN: 1,040 | NLJOIN: 4,368 | +3,328 |

Thus even a tiny join can get worse, and even matching statistics can be
insufficient. Conversely, targeted tiny and asymmetric joins showed that always
choosing hashing would waste work. The join proof also leaves a resource caveat:
MiniVM accounts work differently for the algorithms near execution limits.
Documented semantic equivalence does not establish identical resource failures.

Review found a separate implementation bug: Python's broad line splitting
recognized control/Unicode separators inside valid string literals, exposing
literal text as apparent join instructions. Reproduction preceded the LF-only
line-splitting fix; nine separator variants remain tested. The lesson was to
check the VM's parser rules as carefully as the instruction semantics.
[Join results](records/join-selection/RESULTS.md) and the
[rule and cost model](docs/optimizer.md) retain the measurements and proof boundary.

## Cost-model refinement and the decision to set it aside

The skewed-string loss was a prediction problem, so we investigated a better
prediction without adding another semantic rewrite. We then compared the added
complexity against gains and losses on data kept outside the original fixed set.

Commit `48ae105` explored common-value string-length profiles. In the troublesome
case, each side has 63 empty strings and one 10,000-byte string. Each mean really
is 156.25 bytes, but `min(mean lengths)` is not `mean(pairwise shorter lengths)`.
The simple estimate charges **640,000 string-byte cycles** across 4,096 pairs;
only the one long/long pair actually contributes, for **10,000**. Hashing processes
the long key on both sides. Full VM totals are 22,180 for nested loops versus
28,852 for hashing. Matching averages did not preserve the distribution needed
to predict cost.

The refinement separated NULLs, reported common values and a residual mean-length
bucket, then estimated weighted pairwise shorter lengths. It also handled rounded
averages and discarded profiles after operations that could change the
distribution. The reviewer independently derived the skew explanation. The
refinement passed **59 evaluator and 41 adversarial tests** at that milestone.
These checks support result preservation; the following table measures cost.

All four policies ran on the same eight examples plus eleven targeted workloads,
with **join selection only** and exact output checks:

| Fixed corpus | Simple rule | Refined rule | Always HJOIN | Always NLJOIN |
|---|---:|---:|---:|---:|
| Eight supplied examples | 60,167 | 60,167 | 60,567 | 72,953 |
| Eleven targeted cases | 52,666 | 45,994 | 77,396 | 376,846 |
| All 19 | 112,833 | 106,161 | 137,963 | 449,799 |

No policy wins every individual case. On q0001, always-NLJOIN uses 13,258 cycles
versus the selected 13,570. On the large case with missing statistics, the rule
retains NLJOIN at 4,368 while always-HJOIN uses 1,040. These limitations are
visible in the per-case record rather than hidden by the aggregate.

Only the matching-statistics skew case changed: 6,672 cycles saved, eighteen
unchanged. That looked encouraging until separate **holdouts**, additional
validation workloads, tested NULLs, UTF-8 bytes, truncated distributions, rounding
and stale profiles. One stale-profile case changed 9,232 → 16,528: a loss of
7,296 cycles relative to the simple rule. The schema described skew, but the
runtime data contained short strings instead.

Both the reversal and the broader evidence matter:

| Diagnostic set, join selection only | Simple | Refined | Refined minus simple |
|---|---:|---:|---:|
| Fixed 19 | 112,833 | 106,161 | −6,672 |
| Stale-profile holdout alone | 9,232 | 16,528 | +7,296 |
| Fixed 19 plus that holdout | 122,065 | 122,689 | +624 |
| All 10 holdouts | 229,120 | 222,399 | −6,721 |
| All 29 measured cases | 341,953 | 328,560 | −13,393 |

The holdout loss exceeds the fixed-set gain, but all measured cases together
favor the refinement. Neither unweighted collection represents real workload
frequencies, and several tail cases are related. A tail not described by the
reported common values still defeats the residual-mean approximation: the
truncated-common case keeps HJOIN at 21,358 cycles versus NLJOIN at 18,655, under
both simple and refined rules. More precise snapshot statistics also cannot
guarantee a good decision after drift.

Commit `0990017` restored the simple policy: roughly 100 fewer active lines,
no loss on the supplied examples, and fewer distribution/rounding assumptions
within this assignment's scope. This was a complexity decision, not evidence
that the simple model is generally faster. We stopped tuning to particular
cases and moved to guaranteed work removal. The exact experimental source and
its tests remain in [experiments/](experiments/README.md); the
[full comparison](records/join-costs/RESULTS.md) and
[combined raw totals](records/join-costs/combined.json) preserve the favorable and
unfavorable evidence.

To compare the archived refinement with the simple reference on identical data:

```sh
review_dir="$(mktemp -d)"
python3 tools/compare_join_policies.py --optimizer experiments/profile_optimizer.py --reference-commit 3155414 --output "$review_dir/profile-fixed.json"
python3 tools/compare_join_policies.py --optimizer experiments/profile_optimizer.py --reference-commit 3155414 --holdouts-only --output "$review_dir/profile-holdouts.json"
```

These reproduce the historical policy comparison, not the final full pipeline.

## Dead-code elimination

An unused calculation looks safe to delete, but it may still raise an error or
release memory. This stage taught us that “nobody reads the answer” is not enough
to establish that removing the instruction is harmless.

Commit `0990017` added [dead_code.py](dead_code.py). **Liveness analysis** works
backwards to determine which register values later instructions still need.
Removal additionally requires a narrow whitelist of operations proved **total**,
meaning they cannot raise a semantic error under established input conditions.
Examples include valid stored-column loads, position generation, slices with validated literal
counts, selected typed string functions and date-part extraction. Guaranteed
declarations and instruction postconditions establish types; statistics do not.
Potentially failing retained instructions keep all their dependencies live.
Arithmetic, gathers, joins, groups and unproved sorts remain even when unused.
Unknown syntax disables the pass.

The first candidate still failed at a resource boundary. Eight 2,000-by-2,000
hash joins produced large columns. Small, apparently dead register overwrites
released the old join outputs. Removing those overwrites kept old values resident
until the program exceeded **64 million stored register values**. The original
succeeded and the candidate failed: a concrete correctness defect, not an
ambiguity about an already-failing original.

The fix permits removal only at a register's **first textual definition**.
Every prior write counts, including both join outputs and instructions later
deleted. All overwrites remain, preserving the old-value release point. The
retained heavy witness now has original/current success with equal results and
64,226,104 cycles. Both specialists inspected this guard and added lightweight
regressions; they did not repeat the heavy probe.

Measured separately against **simple joins only**, DCE reduced the eight examples
from **60,167 → 59,891**, saving 276 cycles: three improved, five unchanged.
The 29 prior join cases stayed in the benchmark; three explicitly labeled DCE
positive cases made 32. All targeted join cases and holdouts had zero incremental
DCE change. Historical verification passed **75 evaluator and 57 adversarial
tests**. These results justified keeping the narrow rule and considering another
optimization based on a guarantee, rather than broadening deletion.

The [DCE proof](docs/dce.md), [results](records/dce/RESULTS.md), and
[before-fix lifetime witness](records/dce/lifetime-before-fix.json) preserve the
preconditions and failure. Replay the successful original/current comparison with:

```sh
python3 tools/reproduce_dce_lifetime.py
```

The optional `--include-unsafe` also runs the saved failing candidate and may use
roughly 1 GiB of memory. It is not part of the default suite.

## Sorted-order optimization

If the data is already guaranteed to be in the requested order, sorting it again
wastes work. We used that guarantee while preserving where results are written
and when old register values are released.

Commit `49c7048` added [sorted_order.py](sorted_order.py). A **stable sort** keeps
tied rows in their original order. For direct loads from one table, an exact
nonempty leading prefix of guaranteed `sorted` columns, all `ASC NF` (ascending,
NULLs first), already has that stable order. Its position result is exactly
`0,1,...,N-1`, which `IOTA` generates. Stored types and same-table lengths preserve
the removed sort's type/length checks. The destination write remains, including
when it aliases a key; every write invalidates previous load-origin facts.

A sorted suffix is not a sorted prefix. Derived keys, mixed tables, descending
order, NULLs-last order and merely observed/statistical sortedness do not qualify.
The pipeline became join selection → stored-order replacement → guarded DCE.
Subsequent DCE may remove a newly unused first-definition key load or IOTA, so
measured stage savings include those interactions, not only sort instructions.

Against **joins plus DCE with the new rule disabled**, the eight examples changed
**59,891 → 59,121**, saving 770 cycles in q0001; the other seven were unchanged.
All 32 prior diagnostics remained. Seven separately labeled sort diagnostics
expanded the set to 39: **six improved, 33 were unchanged, none regressed relative
to that preceding pipeline**. This does not erase join regressions versus original
programs or competing algorithms.

Review uncovered another parser mismatch. Python strips certain control
characters MiniVM rejects, and Unicode case conversion can treat lookalikes such
as `AſC` as `ASC`. A Kelvin-sign identifier exposed the same weakness in DCE.
These could turn a source error into a successful optimized program. Seven
failures were reproduced before tightening the shared scanner outside quoted
strings/comments. Literal data and valid VM whitespace remain supported. A
29-codepoint whitespace probe preserved VM success/failure outcomes.

Historical full suites passed **75 + 75 = 150 tests**. The reviewer independently
checked the proof and parser fix; the evaluator specialist independently reran
the reviewer's 16 focused tests and the public suite. Those were independent
reruns, not a separately authored evaluator SORT fixture set: temporary specialist
usage limits interrupted that planned work. The
[sort proof](docs/sorted-order.md), [results](records/sorted-order/RESULTS.md),
[parser witnesses](records/sorted-order/parser-failures-before.json) and
[returned specialist log](records/sorted-order/REVIEW_LOG.md) distinguish actual
execution from planned work. With the approved scope complete, we froze rewrites
and prepared a fresh-reviewer handoff in `fc300d2`.

## Independent review and subsequent fixes

A fresh review checked the finished system rather than accepting its passing
tests as proof. It found two small but consequential ways to make an apparently
correct comparison or rewrite fail.

The [review of `49c7048`](records/post-review/supplied-REVIEW.md), performed with
documentation HEAD `fc300d2`, reproduced both findings through public commands.
We read that report before editing and had the original specialists independently
reproduce and challenge the fixes.

First, changing `HJOIN` to `NLJOIN` adds one byte. A successful program at the
inclusive **4 MiB (4,194,304-byte) file limit** became too large and failed before
execution. Commit `af12e15` added a final UTF-8 encoded-size guard after all passes;
if the candidate exceeds the limit, it emits original bytes. Checking last lets
DCE offset growth when possible. Five boundary tests cover exact-limit fallback,
a candidate exactly at the limit, multibyte comments, all three modes and normal
small joins. The witness now succeeds with original rows and 27 cycles.

Second, the evaluator handed its original-program file to the optimizer, then
executed that same path as its oracle. An optimizer that edited its input and
printed a wrong division rewrite could be compared with itself and falsely pass
all 26 cases. Corrupting the input while printing correct source could conversely
cause false rejection. Commit `b95985d` gives each invocation its own input copy
and creates a separate pristine baseline from in-memory source after the optimizer
exits. Saved expected results now correspond to the saved original source even
with ordinary writes, read-only replacement or input deletion. This isolates input
mutation; it is not a sandbox against malicious processes with the same user's
permissions.

Four evaluator-owned and three independent reviewer mutation tests cover these
outcomes, including replaying pristine failure fixtures. Both supplied wrong
optimizers now exit 1. The reviewer signed off on both fixes; the final counts
below include the twelve new tests across the two issues. The
[post-review results](records/post-review/RESULTS.md) and
[specialist review](tests/adversarial/POST_REVIEW.md) retain before/after evidence.
To replay the supplied mutants, each of these commands should exit 1:

```sh
./evaluate records/post-review/inplace-wrong-optimizer
./evaluate records/post-review/nonmutating-wrong-optimizer
```

## Final verification and results

The final fixes preserve the measured savings and correct the discovered failures.
Performance and correctness remain separate conclusions, each tied to its own
checks and baseline.

The following totals reconstruct the eight-example history. Each row compares
with the preceding row; the refined join experiment had the same example total
as simple joins and is not part of the final pipeline.

| Stage | Example cycles | Incremental saving | Evidence |
|---|---:|---:|---|
| Original / identity | 60,363 | 0 | [baseline JSON](records/benchmark-baseline.json) |
| Simple joins only | 60,167 | 196 | [join JSON](records/join-selection/examples.json) |
| Simple joins + DCE | 59,891 | 276 | [DCE JSON](records/dce/examples-full.json) |
| Final joins + stored order + DCE | 59,121 | 770 | [post-review JSON](records/post-review/examples.json) |

Final results by supplied program, always against its unoptimized original:

| Program | Original | Final | Saved |
|---|---:|---:|---:|
| q0001 | 13,766 | 12,766 | 1,000 |
| q0002 | 3,617 | 3,527 | 90 |
| q0003 | 8,562 | 8,562 | 0 |
| q0004 | 18,442 | 18,442 | 0 |
| q0005 | 5,518 | 5,518 | 0 |
| q0006 | 6,338 | 6,338 | 0 |
| q0007 | 2,596 | 2,444 | 152 |
| q0008 | 1,524 | 1,524 | 0 |
| **Total** | **60,363** | **59,121** | **1,242** |

The final recorded checks at the reviewed source were:

| Correctness / integration check | Recorded outcome |
|---|---|
| Evaluator suite | 79 tests passed, 32.378s |
| Independent adversarial suite | 83 tests passed, 27.368s |
| Public evaluator with current optimizer | 26 cases / 70 execution pairs, 5.967s internal wall time |
| Command-interface baseline checks | Identity/current accepted; all five baseline mutants rejected |
| New input-mutation mutants | Both supplied wrong commands rejected; correct in-place controls accepted |
| Diagnostic benchmark | 39 exact-output cases pass; all join holdouts retained |

[Raw test output and receipts](records/post-review/RESULTS.md) preserve the exact
commands, witnesses and timings. The benchmark compares exact complete results;
the independent evaluator separately tests tolerance, multiplicity, ordering,
malformed output, subprocess failures, timeouts and the overall deadline.

Optimizer calls on examples measured roughly **85–89 ms** in the post-review run;
evaluator wall time includes schema validation and repeated subprocesses. Checks
ran concurrently and process startup is included, so these timings do not prove
an elapsed-time speedup. The earlier optimizer-only 20,000-instruction /
20,000-column probe took 0.445s; that is a scale observation, not a worst-case
60-second bound or a VM-equivalence test. A fresh full-history local clone at
`49c7048` passed the then-current 150 tests and public suite on the same host;
that [setup audit](records/submission-audit/clean-checkout.json) predates the review
fixes and is not a second-platform check.

## Limitations and submission

The project is ready to inspect and reproduce, with its known gaps kept explicit.
A passing finite suite cannot guarantee correct behavior on every valid program,
and a small diagnostic collection cannot predict production performance.

The main remaining technical limitations are:

- Join estimates can regress even with matching statistics; stale statistics and
  unknown string tails remain risks. Always-HJOIN and always-NLJOIN also lose on
  some measured inputs. The final policy is intentionally simple.
- The assignment leaves ordering intent, the relative-error denominator and
  failing/resource-limited program equivalence underspecified. Adopted policies
  are in the [contract](records/CONTRACT.md). Join work accounting and all resource
  boundaries are not universally proved equivalent.
- The evaluator's 10-second VM timeout is a harness policy, not an assignment
  requirement. A candidate timeout is treated as a defect; the fresh reviewer
  did not reproduce a valid equivalent candidate exceeding it. That remains a
  false-rejection concern, distinct from the confirmed and fixed mutation bug.
- VM JSON lacks complete type tags. Fixture metadata cannot always distinguish
  a STR and a numeric value with identical JSON representations; general mixed-type output
  inference and arbitrary-schema generation remain limited.
- DCE's first-definition restriction leaves removable work behind. Stronger
  sorted-order proofs, identity gathers, common-subexpression reuse (avoiding
  repeated calculations), TOPK rewrites and algebraic simplifications are deferred
  until their error, version and lifetime preconditions can be enforced.
- Execution was verified on one macOS host, without a completed Linux or Windows
  run. Process handling is POSIX-specific and is not a security sandbox.

Git preserves the original starter and meaningful milestones; nothing was
force-pushed or silently redirected. The requested origin is
`https://github.com/armaankols/minivm-optimizer.git`. The user confirmed earlier
pushes, but the latest recorded remote check still failed GitHub DNS resolution.
Final publication and reviewer access therefore require user confirmation.
Binaries, including the whole local `bin/`, stay out of the submission.

Submit the source, scripts, tests, docs, development records and Git history.
The [submission checklist](SUBMISSION_CHECKLIST.md) flags remaining human-supplied
information: exact AI settings/usage, a full conversation export if available,
and final publication/any portal-specific packaging requirements. Available
prompts and logs are curated rather than an exhaustive provider export; this
report does not claim missing material has been supplied.

## AI use and further work

AI assisted implementation and review throughout, while the user chose scope and
reviewed tradeoffs. We recorded what is known about that assistance and left
unavailable usage information unfilled.

The recorded runtime identified Codex as based on the **GPT-6 family**. This is
not an authoritative exact backend model ID. The coordinator and two specialists
inherited their configuration without requested model overrides; exact model IDs,
reasoning settings, approximate total tokens and spend remain **pending user or
account information**. The user said they would provide those details later.
No token counts, cost estimates or human-time totals have been invented. See
[AI_USAGE.md](AI_USAGE.md) and the linked prompts, session record and specialist
reports for the available development history.

With a few days and unlimited compute/tokens, the priority would be stronger
independent evidence: generate more schemas and programs, mutate optimizers to
challenge the evaluator, automatically shrink failures to small witnesses, and
exhaustively test small state spaces. Explicit type, row-domain, register-version
and resource-lifetime analysis should precede broader rewrites. A larger fixed
holdout collection, with workload frequencies and uncertainty analysis, should
precede cost-model complexity. Only after those foundations would we revisit
identity gathers or repeated-expression reuse. More testing would strengthen the
evidence; it would not replace a soundness argument.
