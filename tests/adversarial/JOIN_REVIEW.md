# Independent join-selection review

Authorized scope: choose NLJOIN or HJOIN only; preserve every other source byte.
Reviewer owns only `tests/adversarial/**`. No optimizer, evaluator, helper, Git,
or binary edits were made by this agent. No delegation.

## Contract checked independently

`docs/instructions/joins.md:19` explicitly gives both algorithms the same ordered
(left position, right position) pairs, duplicate multiplicity, NULL/NULLEQ
behavior, exact numeric comparisons, incompatible-type errors, and same-register
destination behavior. Therefore choosing between algorithms does not rely on
statistics being true constraints. Statistics affect estimated cost only.

`docs/cycles.md:11` adds four cycles per instruction. Join cost is n*m plus
shorter-string bytes for nested loops, or six plus key-string bytes per input
row for hash join; both charge two per output pair. With two direct LOADs and OUT,
unique equal-sized INT keys produce:

| Rows on each side | NLJOIN total cycles | HJOIN total cycles |
| --- | ---: | ---: |
| 2 | 28 | 48 |
| 64 | 4368 | 1040 |

These values were observed in executable tests, independently calculated from
the cost documentation, and asserted by `test_small_and_large_raw_algorithm_costs`.

`docs/running.md:23` says HJOIN consumes the work allowance faster than its
reported cycles suggest. Semantic-error equivalence is documented; behavior at
resource boundaries remains a limitation, not something finite tests prove.

## Executable coverage

`test_join_selection.py` tests through `./optimize program schema` and the supplied
VM, without importing optimizer code. It covers:

- Twenty seeded pairs of small random columns (seed 44119), both NULL policies,
  both algorithms: 80 VM executions checked against an independently constructed
  ordered Cartesian-pair oracle.
- Duplicate pairs, empty sides, NULL-only keys, mixed INT/NUM scales and precise
  non-equality, and an INT key above the decimal-conversion bound.
- Incompatible non-NULL types and computed heterogeneous keys; corresponding
  empty/NULL cases that suppress those errors.
- Same output register, output/input aliases, join overwrites, subsequent LOAD
  reassignments, and conservative unknown output estimates.
- CRLF, no final newline, opcode/flag case, tabs/spaces, Unicode comments, escaped
  quotes and semicolon/comma/join text inside STR, and a DATE literal. Every source
  byte except the selected join opcode must survive.
- Missing estimates, matching-statistics cost decisions, and deliberately stale
  statistics that cause measurable cost regressions without changing rows.

## Commands and results

From the bundle root:

```
python3 -m unittest discover -s tests/adversarial -p test_join_selection.py -v
```

Initial run, before optimizer implementation existed: nine tests ran in 1.038
seconds; six passed and three were expected red against the identity stub.
The red tests required an actual opcode choice, lexical preservation of that
choice, and a stale-statistics cost regression after choosing. This was baseline
evidence, not a reported implementation defect. Two additional reassignment/
unknown-output-estimate tests were then added while implementation was pending.

Implementation review and final rerun results will be recorded here before the
milestone is declared complete.

First implementation run: 11 tests in 1.782 seconds, 10 passed. One fixture's
expectation was too strict: the implementation now legitimately propagates a
uniform-NDV join-output cardinality estimate when all input rows/NDVs are known.
The test had assumed all join outputs were unknown. Corrected the fixture to
omit NDV while retaining input row estimates, so the first join is estimable and
its overwritten output registers truly become unknown for the next join. This
was a test correction, not an optimizer defect.

## Confirmed correctness failure before fix

`optimizer.py` used Python `str.splitlines(keepends=True)` as the physical VM line
splitter. Python treats additional characters as line boundaries that MiniVM
accepts inside STR data. A valid program can therefore contain fake LOAD and
NLJOIN text inside a literal; the optimizer interprets that text as instructions
and changes the literal's NLJOIN to HJOIN. Both VM programs succeed, but output
strings differ. The reproduction is retained in
`test_non_lf_separator_inside_literal_is_not_an_instruction`.

With `<SEP>` substituted by any character listed below, and valid 64-row INT
tables `l.k` and `r.k`, the complete source is:

```
LOAD z,l.k
FILL text,'prefix<SEP>LOAD x,l.k<SEP>LOAD y,r.k<SEP>NLJOIN a,b,x,y<SEP>suffix',z
OUT text
```

Confirmed independently before the fix for nine non-LF separators: bare CR,
vertical tab, form feed, ASCII FS/GS/RS, U+0085 NEL, U+2028 LS, U+2029 PS. These
are data inside the literal; the actual physical instruction separator is LF.
The first four-separator retained regression run executed 12 tests in 5.228
seconds and failed all four separator subtests; the other 11 tests passed. A
separate pre-fix probe confirmed the remaining five. Coordinator was notified
before changing implementation. The regression was expanded to all nine.

Separate suspected runtime gap: schema loading rescans column stats for every
column (quadratic with column count). This has not been reproduced as a >60-second
failure and is not counted as a confirmed defect. It was reported to coordinator
as a possible cheap robustness improvement.

## Fix review and final verification

Coordinator reproduced the four retained failures before editing the optimizer.
The fix splits only on LF and restores each original LF byte; CRLF and bare CR
inside literals survive. Reviewer inspected this code and independently reran all
nine separator variants: all passed. The schema stats lookup was also changed to
one case-folded dictionary per table; the quadratic scan was removed. No claimed
60-second failure or measured speedup is attributed to that preventive change.

Post-fix join-only command above: **12 tests passed in 2.703 seconds**. Matching
statistics select NLJOIN at n=2 (48 -> 28 cycles) and HJOIN at n=64 (4368 -> 1040).
The exact opcode-only byte test, alias invalidation with truly unknown NDV,
latest LOAD estimate test, all numeric/type-error checks, and independent pair
oracles pass.

Stale-statistics performance regressions were observed and retained separately
from correctness failures:

| Estimated rows/side | Actual rows/side | Original -> chosen | Cycles before -> after |
| ---: | ---: | --- | ---: |
| 64 | 2 | NLJOIN -> HJOIN | 28 -> 48 |
| 2 | 64 | HJOIN -> NLJOIN | 1040 -> 4368 |

Both alternatives obey the same table/column declarations; their statistics
differ. Their exact ordered output pairs agree. These regressions illustrate why
stats justify a performance choice, never semantic equivalence.

During the milestone the evaluator owner confirmed that a correct identity
optimizer producing 300000 stderr bytes was falsely classified as defective.
Coordinator authorized a narrow separate fix: retain only a bounded diagnostic
prefix, drain excess stderr under the original deadline, keep stdout overflow
fatal. Reviewer inspected the fix and added independent external noisy-identity
acceptance and process tests: stderr remains bounded at 20 bytes in the probe,
stdout remains intact, and exit codes 0 and 7 are preserved. The reviewer did not
capture an independent pre-fix execution of this failure; evaluator owner and
coordinator supplied the confirmed reproduction.

Final combined command:

```
python3 -m unittest discover -s tests/adversarial -v
```

**31 tests passed in 4.902 seconds**, covering prior evaluator/semantic regressions,
the 12 join-selection tests, and the two new stderr challenges. No unresolved
correctness failure is confirmed in the reviewed implementation.

## Limits and remaining risks

- Tests are finite evidence, not a proof; no resource-boundary equivalence claim.
- Heuristic NDV, 50% IDX selectivity, carried string lengths, and min(mean string
  bytes) can make poor decisions on skewed or stale data. This affects cycles,
  not the documented equivalence of the unchanged join operands.
- Missing/incompatible estimates leave the original algorithm unchanged. Aggregate
  cardinalities remain unmodeled; broad filter/join/order rewrites are outside scope.
- The actual public evaluator has its own finite-program coverage and mixed-output
  serialization limitations, documented in `REVIEW.md`. No Windows run was made.
- No binary is part of these review artifacts. Interpreter binaries remain local.
