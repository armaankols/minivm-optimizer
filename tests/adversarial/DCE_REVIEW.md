# Conservative dead-computation review

Authorized scope: investigate proven-total dead-computation elimination after
the join-cost experiment; no optimizer/shared-helper/Git edits or delegation.
Reviewer owns `tests/adversarial/**` only.

## Minimum whitelist proposed before implementation

Do not use estimated cardinality, null counts, min/max, or common values as proof
of safety. Use guaranteed schema declarations and versioned register facts.
All rules below require a syntactically valid instruction, destination register,
correct operand arity, and a dead destination at that program point.

| Instruction | Necessary semantic preconditions |
| --- | --- |
| LOAD | Referenced table/column guaranteed present in schema; valid column destination. Names compare case-insensitively for stored columns. |
| IOTA | Source proven to be a defined column, not a group set or undefined register. |
| SLICE | Defined column source; count is a fully valid nonnegative integer literal. Arbitrarily large counts are valid. |
| UPPER, RTRIM, TRIM, LEN, NULLIFE | Defined homogeneous STR-or-NULL column source. A scalar literal alone does not meet element-wise register requirements. |
| LEFT, SUBSTR | Same STR column proof; LEFT count and SUBSTR length are valid nonnegative integer literals; SUBSTR start is at least one. |
| Optional ISNULL | Any defined column source; group sets and undefined registers remain errors. |

Coordinator's accepted initial whitelist also includes YEAR/MONTH/DAY/DOW on a
defined DATE-or-NULL column. Valid stored calendar dates guarantee valid parts;
the result is an INT column with the same length. No FILL, GATHER, arithmetic,
TRUNC, SORT, join, or group instruction is deemed total in this initial pass.
Removed instructions become blank lines, preserving their trailing comments and
original newline bytes, so line numbers remain stable.

Initially defer FILL unless its literal is fully validated: the join estimator's
literal classifier recognizes integer/decimal/date spellings without proving
their ranges or calendar validity. INT overflow, inexact/overflowing NUM, and
invalid dates must not disappear merely because a destination is dead. A safe
small FILL subset is NULL, BOOL, quoted STR, and fully checked INT; NUM/date can
stay opaque until validation is justified.

Initially defer GATHER unless index validity is established by provenance, not
statistics. A minimum proof is IOTA over the same unchanged source column (or a
proven equal row domain); every position then lies in range. NULL, non-INT and
out-of-range indexes, index/source reassignment, and different table lengths are
errors. General SORT/IDX/join/group index provenance is outside the first scope.

Retain arithmetic, joins, grouping/aggregates, and any other computation whose
semantic error preconditions are not proved. Their inputs stay live even if their
outputs are dead. Merely unused does not mean removable.

## Documentation and proof obligations

- `docs/instructions/README.md:20-30`: wrong register kind/undefined register,
  equal-length register operands, at least one element-wise register operand,
  NULL-first and row-dependent type errors.
- `docs/instructions/columns.md:23,33,43,63,73`: LOAD/FILL/IOTA/GATHER/SLICE contracts;
  GATHER indexes must be in-range INTs.
- `docs/instructions/strings.md`: homogeneous STR operations; LEFT/SUBSTR character
  semantics, Unicode uppercase expansion, only ASCII space trimming.
- `docs/language.md:45-48,64-79`: mutable register names, literal ranges, and
  unbounded nonnegative integer operands.
- `docs/values.md:12,27-38`: INT128 and NUM range/rounding/conversion errors.
- `docs/running.md:112-125,168`: declarations constrain all valid datasets;
  statistics do not. `running.md:15-32` supplies resource limits and error behavior.

Backward liveness must kill destinations before adding source uses for retained
instructions. This preserves old definitions in read/write aliases such as
`IOTA x,x`. Join instructions define both destinations, including the same-name
case. Removed instructions do not keep their own source chains artificially
live. Forward kind/shape facts must reflect each definition, not the final value
of a reused register name. Unknown syntax/opcodes should be a conservative
barrier or make the whole DCE pass fall back.

Only semantic totality is claimed. Removing even a safe LOAD/string operation can
avoid a prior memory/work-limit failure; the assignment does not define full
resource-error equivalence. This caveat is separate from preserving dead DIV,
type, invalid-index, and malformed-literal failures.

A later confirmed finding below shows that merely declaring resource limits out
of scope is insufficient: removal must not extend an old register's lifetime and
introduce an error on an originally successful program. The final guard allows
removal only at a register's first textual definition.

Executable probes, implementation enforcement review, and test/failure chronology
will be appended after fixtures and the coordinator candidate are available.

## Independent pre-implementation baseline

Added `test_dead_computation.py` before implementation. Command:

```
python3 -m unittest discover -s tests/adversarial -p test_dead_computation.py -v
```

Twelve methods ran in 6.791 seconds. Nine passed; three were expected red because
the existing optimizer did no DCE: whitelist-chain removal, read/write-alias chain
removal, and CRLF/control-separator removal of an unused LOAD. The last method has
nine separator subtests, for eleven expected failing assertions in total. These
are baseline assertions, not an implemented-optimizer failure.

Original/candidate VM probes confirmed dead DIV/MOD/overflow failures, missing
columns, group/undefined sources, wrong type/invalid count failures, malformed
FILL INT/NUM/date/string literals, invalid indexes, mismatched CAT lengths, and
frozen-empty-statistics witnesses. Erroring originals are compared for failure
status/no result, rather than mistaken for valid successful fixtures. Explicit
nonwhitelist tests retain FILL/GATHER/arithmetic/TRUNC/SORT/joins/groups even when
they happen to succeed in these small inputs. Unknown opcode tests require the
entire DCE stage to fall back.

## Candidate implementation review

Independently read `dead_code.py` and the CLI integration after the ready signal.
The candidate implements the agreed whitelist without expansion. Guaranteed
stored column declarations provide forward facts; malformed/ambiguous declarations
disable the pass. No statistics are read by this proof analysis. Facts are simple
column kinds, read before each instruction's destinations are invalidated. Every
unmodeled destination becomes unknown, including both join outputs and group sets.

The known-opcode role table handles OUT, both join destinations, SORT/TOPK keys,
GROUP keys, literals/count positions, and scalar/group/aggregate operands. Unknown
syntax or opcodes disable the whole DCE stage. Nonwhitelist instructions are
retained with their input dependencies; the backward walk kills written names
before adding reads. Removed safe instructions do not keep their now-dead source
chains live. Physical parsing uses LF only. Whitelist removals preserve trailing
comments and original CRLF/LF bytes, so source line numbers remain unchanged.

Default `./optimize program schema` runs the frozen simple join policy followed
by DCE. `./optimize --joins-only program schema` isolates the prior join stage.
The exact profile experiment remains executable under
`experiments/profile_optimizer.py`; all profile holdout tests still exercise it.
No coverage or historical performance loss was deleted during this activation.

## Verification and result

Initial candidate run: all original twelve DCE methods passed in 6.699 seconds.
Added two independent dependency/alias methods to challenge retained SORT/TOPK,
GROUP, FILL, join, IF, CAT and GSUM consumers of removable inputs, and to verify
join writes kill both old destination values while preserving aliased old inputs.
All fourteen DCE methods then passed in 8.304 seconds.

Final command:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
```

**55 tests passed in 15.421 seconds.** This includes active DCE, simple join-only
selection, archived profile experiments with every holdout, all prior literal
corruption witnesses, independent evaluator challenges, and semantic boundaries.
Positive DCE cases have fewer cycles and identical exact ncols/ordered rows,
including duplicate rows, repeated output columns, NULLs and register overwrites.
Error cases retain failure status and produce no result. No implementation failure
was confirmed at this initial checkpoint. The later coordinator lifetime finding,
fix and independently retained guard regressions are recorded below; the initial
checkpoint must not be read as a final soundness conclusion. Baseline expected-red
assertions are logged separately above.

## Remaining risks and deferred work

- Finite tests do not prove soundness. Full resource-failure equivalence is not
  claimed; deleting total computations can avoid memory/work exhaustion.
- FILL/GATHER/arithmetic/TRUNC/SORT/joins/groups deliberately remain even when
  particular inputs make them harmless. Larger reductions need separate proofs.
- Conservative unknown facts and whole-pass fallback miss optimization
  opportunities. They must not be replaced by sampled row counts or observed
  all-NULL/empty data without a guaranteed proof.
- Statement syntax/liveness and forward type facts remain the important review
  surfaces if new opcodes or whitelist rules are added. Keep known roles exact
  and unknown operations conservative.
- The coordinator measures representative benchmark cycles and optimizer/evaluator
  wall time separately; the test-suite timings here are verification timings.

## Confirmed overwrite-lifetime failure and correction

Before finalization, coordinator independently identified and executed a resource
counterexample. Saved complete original/candidate programs and process outcomes
are in `records/dce/lifetime-before-fix.json`: eight HJOINs on 2000 constant INT
keys per side each produce two four-million-position columns. Small dead LOADs
overwrite both join destinations after each join. Original exits 0 in
0.449912333 seconds. The first DCE candidate deletes those overwrites, leaving
the old large columns resident; candidate exits 1 in 0.613154625 seconds at line 23:
`HJOIN: the registers would hold more than 64000000 values`. No result is printed.

This is a confirmed optimization soundness failure on a successful original,
not simply avoidance of an original resource failure. Reviewer read the saved
evidence and independently checked the reasoning against `docs/running.md:16-17`.
The heavyweight execution was performed by coordinator, not duplicated by the
reviewer, to avoid unnecessary native allocations approaching 1 GB.

Coordinator's correction records every destination name written in the original
forward scan, including both join destinations and unknown-kind/group writes.
A whitelist instruction is eligible for removal only if none of its destinations
has been written before. This syntactic set is never relaxed because an earlier
definition later becomes dead. Thus removing a first allocation cannot suppress
an explicit overwrite that released an old register value. The reviewer inspected
this guard and found it applied before backward liveness, independently of type
facts and statistics.

Added two lightweight black-box regressions: a small sibling preserves dead
LOAD/ISNULL/IOTA/SLICE overwrites following retained join definitions; removing a
first LOAD does not reclassify its later LOAD overwrite as removable. Updated
only the read/write-alias positive expectation to preserve its overwrite chain.
All semantic negative tests remain unchanged. Sixteen DCE methods passed in
7.925 seconds after this correction. Final combined rerun using the command above:
**57 tests passed in 15.700 seconds**. No additional failure was confirmed in this
post-fix review. The coordinator owns the heavyweight fixed-witness rerun and
representative benchmark verification; no result for those unexecuted-by-reviewer
commands is invented here.

During the subsequent guaranteed-order review, independent probes found another
error-preservation issue in shared operand parsing: Python `.strip()` removes
U+001C..U+001F while the VM rejects them. A dead `LOAD dead,t.x<FS>` was incorrectly
considered valid and removed. All four controls were reproduced before the parser
fix and retained in `test_python_only_whitespace_does_not_validate_malformed_load`.
This is tracked with the related SORT parse-error finding and fix provenance in
`SORT_REVIEW.md`; earlier finite passing-test checkpoints are historical evidence.
