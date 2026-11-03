# Frozen join policy

The active join stage uses the simpler policy from commit `3155414`. The
profile-based model from `48ae105` is archived in `experiments/`, with every
measurement and holdout retained. See `records/join-costs/RESULTS.md` for the
balanced combined comparison and engineering recommendation. This choice does
not claim the simpler model predicts production performance better.

`./optimize --joins-only PROGRAM SCHEMA` isolates this stage. The required
two-argument command runs this stage first, then the conservative dead-code pass
described in [dce.md](dce.md). Source-byte preservation below applies to the join
stage; the dead-code pass can blank proven-safe unused instructions.

The only program rewrite is replacement of an `NLJOIN` opcode with `HJOIN`, or
vice versa. No operands, flags, register names, literals, comments, whitespace,
line endings or other instructions are rewritten.

## Preconditions and correctness argument

Recognize a physical LF-delimited instruction with four register operands and
optional case-insensitive NULLEQ. Quoted strings and escaped quotes protect
commas and semicolons while reading operands. A source opcode is changed only
when both key columns have enough estimated information to compare costs.
Unknown estimates, incompatible estimated types, and exact estimated cost ties
leave the original opcode unchanged.

`instructions/joins.md:19` explicitly guarantees both algorithms produce the same
ordered pairs (left position then right position), preserving duplicate pairs,
NULL/NULLEQ behavior, exact cross-numeric comparison, and semantic errors. If both
destinations alias, both leave the right position column. Inputs are inspected
before recording overwritten destination estimates. No cast or arithmetic is
inserted. All other source bytes survive; therefore subsequent instructions see
the same register values and order. This is the rule's semantic justification.

Declared constraints and statistics are not used to discard pairs or NULLs.
Statistics choose between already equivalent algorithms; they are never asserted
as guarantees about runtime data. As documented in `running.md:23`, resource work
accounting differs, so this argument does not establish identical failure behavior
at resource limits. The assignment's error-equivalence wording remains ambiguous.

## Cost model and estimates

Ignoring the common instruction base cost and two cycles per output pair, for
numeric, DATE and BOOL keys:

```
NLJOIN = L * R
HJOIN  = 6 * (L + R)
```

For STR keys with estimated mean UTF-8 byte lengths bL and bR:

```
NLJOIN ~= L * R * (1 + min(bL, bR))
HJOIN  ~= L * (6 + bL) + R * (6 + bR)
```

`min(mean bytes)` is not `mean(min(bytes))`. This approximation can be poor even when statistics match actual data; the
fixed skewed-string benchmark retains that measured limitation. Stale stats can also cause regressions, including
on tiny joins. Choosing hash unconditionally would have avoidable tiny-join costs.

The implementation tracks estimates in one forward pass. Direct LOADs read table
rows, column type, distinct count and STR average bytes. IOTA, SORT, TOPK, SLICE,
FILL, GATHER and element-wise operations propagate estimated lengths/types.
IDX assumes 50% selectivity. Join output size uses L*R/max(1,NDV_L,NDV_R) when
all required estimates exist, capped by the register limit; otherwise it is
unknown. String transformations carry a rough input-byte estimate. Aggregates
and group sets are not modeled. These approximations affect cost choices only.
Register reassignment replaces old facts; facts are never used to substitute
registers or change operand values. Schema stats are indexed once per table.

## Positive, boundary and adversarial tests

- Tiny numeric HJOIN -> NLJOIN and large numeric NLJOIN -> HJOIN.
- Tiny/asymmetric and larger string joins; equal estimated costs; absent stats.
- Exact ordered Cartesian-pair oracles with duplicates and NULL/NULLEQ.
- Mixed INT/NUM precision and scale; wide derived INT beyond NUM conversion
  bounds; incompatible/noncomparable key errors; empty/all-NULL suppression.
- Identical destination registers, destinations aliasing inputs, overwritten
  join outputs, and subsequent register reassignment.
- CRLF, missing final newline, case and tabs, strings with escaped quotes,
  semicolons, commas and fake join text. Nine non-LF control/Unicode separators
  inside literals are retained as a correctness regression.
- Frozen estimates with changed data, including explicit cost regressions.

Specialist suites invoke `./optimize PROGRAM SCHEMA` and execute original and
candidate with MiniVM, without importing optimizer code. Benchmarks additionally
audit source differences to allow only opcode changes. Seeds and commands are
retained in `tests/adversarial/JOIN_REVIEW.md`,
`tests/evaluator/JOIN_REPORT.md`, and `records/join-selection/`.

The subsequent DCE stage is measured separately; all join holdouts remain in its regression corpus.
