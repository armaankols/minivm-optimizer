# Guaranteed stored-order SORT elimination

The third optimization replaces only eligible SORT instructions with IOTA. The
pipeline is frozen join selection -> stored-order elimination -> conservative
DCE. `--no-sorted-order` runs the same join/DCE stages without this rule, so its
contribution can be measured separately. No identity-GATHER rewrite is included.

## Preconditions and proof

- At least one key, with every mode exactly ASC NF (case-insensitive keywords).
- Each current key definition is a direct LOAD of an existing stored column.
- All key columns belong to the same table, and their sequence exactly matches
  a nonempty leading prefix of that table's guaranteed `sorted` declaration.
- All writes invalidate old LOAD origins, including both join outputs. A later
  valid direct LOAD may establish a new origin. Register names stay case-sensitive;
  stored table/column identifiers compare case-insensitively.

`running.md:121` guarantees stored ASC NF order. `instructions/sorting.md:18,38-42`
specifies stable sorting. The rows therefore already have the required prefix
order; ties, NULLs and equal NUM values with different scales retain input order.
The SORT result is exactly positions 0..N-1, which IOTA produces. Stored types and
same-table columns also establish comparability and equal lengths, so no sort
type/length check is lost. No statistic is used to establish any precondition.

Suffixes, additional keys, DESC, NL, mixed tables, derived keys, missing or malformed
guarantees, unknown operations and undefined/group keys are left alone. Unknown
syntax disables the pass. The implementation does not attempt stronger proofs
from uniqueness, non-nullability, observed row order or selectivity estimates.

The replacement reads key origins before writing the destination, even if that
destination aliases a key. It preserves the same INT column, length, register and
write position, then invalidates the destination's LOAD origin. Later sorts cannot
treat those position values as stored data. This preserves the old-value release
at the write. DCE may subsequently remove newly dead first definitions, but its
overwrite guard still applies to IOTA and now-unused secondary-key LOADs.

## Parsing fixes discovered during review

The reviewer found confirmed error suppression from Python-specific whitespace
and Unicode case folding. FS/GS/RS/US (U+001C..001F) are stripped/split by Python
but rejected by MiniVM; long-s in AſC uppercases to ASC in Python; Kelvin sign in
a stored identifier lowercases to k. These could turn an invalid source into a
successful candidate. The dead-LOAD form also exposed an existing DCE parser bug.

The shared scanner now refuses those controls and non-ASCII non-whitespace token
characters outside quoted strings and comments, disabling proof-based passes for
the affected source. It preserves quoted Unicode/control data, comments and valid
VM Unicode whitespace. Coordinator reproduced seven failures before fixing them;
the retained cases now remain failures. A probe of all 29 Python whitespace
codepoints below U+3001 preserved original/candidate success or failure. This is
bounded evidence, not a claim of a complete MiniVM parser.

## Evidence

The reviewer independently inspected the fix and passed all 16 focused tests; the
evaluator independently reran those tests plus the public 26-case/70-execution
suite. Coordinator full suites pass 150 tests. Coverage includes prefixes, nullable
ties, NUM scales, aliases/reassignment, source bytes, malformed tokens and the DCE
lifetime boundary. All existing join holdouts are retained. See
`records/sorted-order/RESULTS.md` and the specialist review log for exact results.
