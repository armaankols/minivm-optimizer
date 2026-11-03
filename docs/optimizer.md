# Join algorithm selection

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

For STR keys with estimated all-row mean UTF-8 byte lengths bL and bR:

```
NLJOIN ~= L * R * (1 + sum(p_i * q_j * min(length_i, length_j)))
HJOIN  ~= L * (6 + bL) + R * (6 + bR)
```

The sum uses a small length-frequency profile for direct LOAD columns: NULL mass
at zero bytes, up to eight reported common values at their UTF-8 byte lengths,
and unlisted non-NULL rows at a residual mean length. `avg_bytes` is a non-NULL
mean; subtract common-value bytes from its implied non-NULL total to estimate
the residual. Profiles have at most ten buckets. Without a profile, the scalar
mean becomes one bucket, retaining the previous fallback model. Valid NULL counts
also adjust the fallback mean to include zero bytes for NULL rows.

Reported averages are rounded to two decimal places. Decimal intervals of
plus/minus .005 times non-NULL count bound the implied total. Total byte counts
are integers; recover a residual sum exactly when only one nonnegative integer
fits. Otherwise retain its mean and rounding slack. Keep the input opcode when
the estimated cost difference is within L*R*(eL+eR)+L*eL+R*eR, where each e is
per-row rounding uncertainty. This guards average-reporting error only.

Duplicate/malformed common values, invalid counts, inconsistent supplied distinct
counts or impossible byte totals discard the profile. Profiles are dropped after
GATHER, SLICE and every element-wise operation; constant STR FILL has an exact
profile. Scalar estimates can survive as an explicitly rough fallback.

The previous `min(mean bytes)` was not `mean(min(bytes))`; it overcharged the seed
skew case by 64 times. Partitioning common values fixes that case. With exact
matching means, residual mean buckets still upper-estimate the NL byte term
because min is concave. That does not prove HJOIN is cheaper: heterogeneous
residuals can still make it a bad choice. Truncated common lists, derived-column
fallbacks and stale stats remain measured limitations. No semantic decision
depends on this distribution estimate being true for the actual runtime data.

The implementation tracks estimates in one forward pass. Direct LOADs read table
rows, column type, distinct count and STR average bytes. IOTA, SORT, TOPK, SLICE,
FILL, GATHER and element-wise operations propagate estimated lengths/types.
IDX assumes 50% selectivity. Join output size uses L*R/max(1,NDV_L,NDV_R) when
all required estimates exist, capped by the register limit; otherwise it is
unknown. String transformations carry only a rough input-byte mean, not a source
distribution. Aggregates
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

The cost refinement also has separate independent tests and before/after policy
comparisons in `tests/adversarial/COST_REVIEW.md`,
`tests/evaluator/COST_REPORT.md`, and `records/join-costs/`.

No other optimizer rewrite is included in this milestone.
