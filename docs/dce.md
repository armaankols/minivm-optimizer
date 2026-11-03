# Proven-total dead computation elimination

The full two-argument optimizer runs this pass **after** frozen join selection.
`--joins-only` provides the baseline for measuring its separate contribution;
join choices cannot change because of DCE. No arithmetic or live-value identity
rewrite is performed.

## Preconditions

An instruction is removable only when all of these hold:

1. Its result is dead under backward register liveness, including reads of every
   retained potentially failing instruction, not just dependencies of OUT.
2. It is a **first textual definition** of its destination register. Every prior
   definition counts, including both join outputs and unknown-kind writes.
3. It belongs to the whitelist below and its source column/type and literal-count
   conditions are proved from guaranteed schema declarations and instruction
   postconditions. Statistical fields are never consulted.

| Instruction | Required guarantee |
|---|---|
| LOAD | Referenced stored column exists in the schema with a valid stored type |
| IOTA, ISNULL | Source is a proven column, not an undefined register or group set |
| SLICE | Proven source column and syntactically valid nonnegative integer count |
| UPPER, RTRIM, TRIM, LEN, NULLIFE | Proven STR column (NULL values permitted) |
| LEFT | Proven STR column and valid nonnegative literal count |
| SUBSTR | Proven STR column, positive literal start, nonnegative literal length |
| YEAR, MONTH, DAY, DOW | Proven DATE column (NULL values permitted) |

Counts can be arbitrarily large; validation does not convert them to a bounded
machine integer. No totality is assumed for FILL, GATHER, arithmetic, TRUNC, SORT,
joins, groups or aggregates. Even dead results of these instructions remain.

## Correctness argument and implementation boundaries

The whitelist operations cannot produce a semantic error once these preconditions
hold. Unary type facts include NULL behavior given by the instruction docs.
IOTA/SLICE/ISNULL operate only on established columns. LOAD existence and stored
types follow declarations, not a particular table's rows or statistics.

Forward facts are replaced at every write; unmodeled outputs become unknown.
Facts are read before aliased writes. A precise defs/uses table handles every
known opcode, including both join destinations, sort keys and group consumers.
Unknown syntax/opcodes disable the whole DCE pass. Backward liveness kills writes
before adding reads, preserving prior versions used by read/write aliases.

For a removable instruction, no retained computation reads that register version,
and the instruction itself cannot fail semantically. Removing it therefore leaves
retained operands, their associations, order, NULLs and OUT structure unchanged.
Keeping inputs of potentially failing instructions live preserves their checks
even when their results are unused. This is why dead DIV or invalid GATHER cannot
be removed merely because OUT does not use them.

### Register lifetime is observable through memory limits

Ordinary liveness alone is insufficient in MiniVM. A dead overwrite may release
an earlier large column. Deleting that overwrite can retain the old value and
introduce a resource failure in an originally successful program. The coordinator
confirmed this with eight 2000-by-2000 HJOINs: the original succeeds, but deleting
small LOAD overwrites leaves join-position columns resident and exceeds 64M values.

The first-definition restriction prevents this lifetime extension. It is based
on **all textual definitions**, not on definitions that survive the pass; the
guard is never relaxed after deleting an earlier first definition. It intentionally
retains harmless-looking overwrites. The confirmed before/after witness is saved
under `records/dce/lifetime-*.json`, with lightweight structural regressions in
both specialist suites. The heavy probe was executed by the coordinator, not
duplicated by the specialists.

Successful source executions should not gain a memory failure from extending an
old register lifetime. Deleting work can still allow a formerly resource-limited
program to finish; the assignment's equivalence contract for failing originals
remains underspecified. The earlier NL/H work-accounting caveat is separate.

## Emission and verification

Removed instructions become blank lines or their original comments, retaining
physical LF/CRLF boundaries, line numbers and final-newline state. No source file
size increase is required. Remaining instruction bytes are preserved.

Tests cover NULL/empty alternatives, wrong types and kinds, overflow/division/date
and index errors, cross-table length mismatch, reassignment and join aliases,
unknown-opcode fallback, Unicode/control characters, comments and line endings.
The benchmark includes all19 fixed join cases, all10 join holdouts, and separately
labeled DCE-positive cases. Each compares the same selected joins with DCE off/on
and requires exact full VM results. Finite tests provide evidence, not a proof.
