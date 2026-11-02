# Baseline comparison and execution contract

Sources: assignment requirements (single page); `docs/running.md`,
`docs/values.md`, and the instruction reference. The assignment PDF and supplied
interpreter builds are intentionally absent from this text-only repository.

## Required public interfaces

- `./optimize PROGRAM SCHEMA`: prints a program; at most 60 seconds.
- `./evaluate OPTIMIZER`: runs that executable with PROGRAM and SCHEMA arguments;
  exits zero if no defects found, nonzero otherwise; at most 15 minutes.
- `bin/minivm PROGRAM DATA`: exit 0 and a JSON result, or exit 1 and stderr.
- `bin/minivm --schema DATA`: verifies data and reports declarations plus stats.

The supplied identity optimizer is unchanged in the first milestone. Evaluator
stdout is a JSON summary. Exit 1 denotes a witnessed optimizer defect; exit 2
denotes usage/infrastructure failure or incomplete evaluation.

## Independence and comparison

The evaluator imports no optimizer code. Fixture programs, declared output types,
and ordered/unordered annotations are evaluator-owned. Original VM executions
provide expected values. Fixture output columns have known homogeneous types;
general mixed-type output inference is outside this baseline suite.

- `ncols`, row counts, row widths, NULLs, BOOLs, strings, and dates are checked.
- Numeric cells use Decimal and symmetric relative tolerance:
  `abs(a-b) <= 0.000001 * max(abs(a), abs(b))`. Zero has no absolute slack.
  The assignment does not define the denominator; this is a documented choice.
- Unordered comparisons match complete rows with duplicate multiplicity.
  Maximum matching avoids greedy failures under non-transitive tolerance.
- Ordered fixtures compare whole rows positionally. Explicit SORT/TOPK outputs
  and directly exposed join position tuples have fixture contracts requiring
  order. Pure no-sort filter/reassignment outputs are unordered. Annotations are
  authored rather than guessed from an arbitrary program's syntax.
- Numeric-looking STR values are exact strings. No string-to-number heuristic is
  used without fixture type information. BOOL is distinct from integer 1/0.
- Cycles are parsed as valid VM metadata, but are not part of result equality.

Baseline-success cases establish the required positive equivalence checks.
Potentially erroring instructions have separate executable semantic witnesses.
This is not a universal comparison engine for arbitrary unknown programs.

## Schema and generators

Only structural declarations and `key`, `not_null`, `refs`, `check`, `sorted`
justify semantic assumptions. Every `stats` field is an estimate.

Each case freezes a schema from its first dataset, runs the optimizer once, then
tests multiple datasets with identical declarations and different statistics.
MiniVM validates every alternative. Fixed seeds are 1729 and 8675309. The suite
uses bounded template families, not a general arbitrary-schema constraint solver.

## Resource management

The evaluator has an internal overall monotonic budget below the required 900
seconds, leaving cleanup/reporting reserve. Individual optimizer calls are capped
at 60 seconds and VM calls at 10 seconds, further capped by remaining budget.
Output capture is bounded; stdout must fit a legal program (4 MiB); stderr is
bounded to avoid an output flood. POSIX process groups are killed and reaped,
including children holding inherited pipes open. The baseline is POSIX-only.

Deadline exhaustion is an incomplete evaluation, not a clean pass. Failed runs
retain text fixtures and captured output (hex when not UTF-8) in the ignored
`.evaluation-failures/` directory. Semantic errors and resource-limit errors are
distinct concerns; assignment equivalence for erroring originals is unspecified.

## First optimization: join algorithm selection

Select the cheaper join algorithm while preserving operands, both destinations,
and NULLEQ exactly. `docs/instructions/joins.md` explicitly guarantees HJOIN and
NLJOIN return identical pairs, pair order, and semantic errors. Stats can choose
between these already equivalent operations. Cost model excludes common output
costs: numeric NLJOIN is approximately L*R versus HJOIN 6*(L+R), plus base cost.
String keys require byte-cost estimates. Tiny joins may favor NLJOIN; do not
blindly replace every NLJOIN. Unknown estimates can leave the opcode unchanged.

Boundary tests should include empty sides, duplicates, NULL/NULLEQ, mixed INT/NUM,
incompatible types, aliased destinations and reassigned inputs. Resource-limit
behavior remains an explicit caveat because the work accounting differs.

The user subsequently authorized this rule. It is implemented in `optimizer.py`;
the exact source-preserving conditions, heuristic propagation and limitations
are described in `docs/optimizer.md`. No second rewrite is included. The baseline
identity executable used for evaluator validation is now a separate independent
fixture rather than the evolving `optimize` command.
