# Independent adversarial review

Scope: baseline milestone only. The reviewer owns `tests/adversarial/**`; no
optimizer, evaluator, shared-helper, Git, or binary changes were made by this
agent. Assignment from coordinator: independently inspect VM semantics; retain
executable counterexamples; challenge the evaluator using external optimizer
commands, independently specified data, and VM execution. No nested delegation.

## Findings and decisions

Confirmed VM witnesses (not defects in the identity optimizer) are retained in
`semantic_witnesses.json` and executed by `test_semantic_witnesses.py`:

- Removing dead `DIV x,0` changes failure to success.
- Replacing SORT+SLICE with TOPK can skip a type error in a discarded key group,
  even for k=1. Homogeneous key proofs matter.
- CSE aliases must preserve old register values after reassignment.
- Guaranteed lexicographic sortedness does not imply a sorted suffix.
- Check bounds constrain non-NULL values only; eliminating the filter may retain
  NULL rows the original removes.
- Self-equality of NULL returns NULL, rather than TRUE.
- NUM reassociation/cancellation can suppress intermediate overflow.
- Joins preserve duplicate pair multiplicity and i-then-j ordering; NULL pairs
  appear only with NULLEQ. NLJOIN and HJOIN agree on this witness.

These eight fixtures contain 17 VM executions. Initial planning reproductions
were made under `/tmp/minivm-review-confirmed/` and independently reproduced by
the coordinator before implementation. The retained JSON contains complete data,
programs and expected outcomes; it has no dependency on those temporary files.

Evaluator code-review finding: `filter` and `reassignment` initially required
ordered comparison despite having no explicit sort. Raised with evaluator owner;
owner changed both to unordered. An external optimizer that sorts complete filter
output rows now passes `test_unsorted_filter_may_reorder_whole_rows`. This was a
source-contract finding, followed by an executable regression after the fix;
there was no recorded pre-fix failing test execution.

Confirmed evaluator robustness failure, reported by coordinator and independently
reproduced before the fix: `cell_equal('1.0','1e1000000','NUM')` and the INT variant
raised raw `decimal.Overflow`. The evaluator also treated whitespace and underscore
Decimal spellings as valid numeric output. Coordinator's external-optimizer
reproduction raised Overflow without saving a witness. Evaluator owner fixed
canonical numeric grammar/length checks and Decimal exception handling. Reviewer
read the fix and reran both direct probes and an external `FILL bad,'1e1000000',x`
optimizer regression; malformed strings now compare unequal, and the optimizer
produces a Defect with a saved witness. Regression tests remain in
`test_evaluator_contract.py`.

Coordinator subsequently confirmed a false rejection introduced by overly strict
INT-slot parsing: stored INT values [1,2,NULL] became NUM ["1.0","2.0",NULL]
through ADD 0.1 followed by SUB 0.1. These numeric values satisfy the assignment.
Evaluator owner unified canonical numeric parsing/tolerance for INT and NUM
slots, keeping BOOL separate and STR exact. The fix had already landed before
the reviewer's independent execution; that execution accepted the external
optimizer. Reviewer read the updated code and retained direct type/scale/tolerance
tests plus an external-optimizer regression on INT32 extremes, NULL, zero, empty
data, and 10 seeded random INT32 values (seed 19741). All pass.

No unresolved evaluator failure was confirmed by the final independent tests.
The tests also establish:

- Duplicate counts, complete-row associations, required order, BOOL versus INT,
  numeric STR versus declared NUM metadata, exact zero, and wide INT encodings.
- Tolerant unordered matching agrees with exhaustive permutation matching on
  100 seeded small cases (seed 65843), including a known greedy-matching trap.
- Duplicate JSON keys, invalid widths, floats, NaN, Boolean ncols, and trailing
  JSON garbage are rejected.
- Identity external optimizer accepts two datasets under one frozen schema.
- An optimizer using frozen stats.rows as a guaranteed slice length is rejected
  on a larger alternative; saved schema retains stats.rows=2 while saved witness
  data has three rows.
- Alternative declarations changing not_null yield incomplete evaluation rather
  than a clean pass.
- Empty program, exit 7, invalid UTF-8, output flood, a child holding pipes open,
  and overall deadline exhaustion receive failure/incomplete outcomes.
- Optimizer paths containing spaces are passed as one argument.

## Commands, failures, and reruns

From the bundle root:

```
python3 -m unittest discover -s tests/adversarial -v
```

- Initial fixture-generation command accidentally used a path relative to the
  workspace root while running from the bundle root. It raised FileNotFoundError;
  the first test run consequently lacked its JSON file. Corrected the destination
  and reran successfully: 1 test, 17 VM executions, 0.156 seconds.
- Added independent evaluator challenges: 11 tests passed in 1.152 seconds.
- Reran after evaluator owner changed ordering/schema checks: 11 passed in 1.108
  seconds.
- Added explicit unordered-filter and changed-declarations regressions:
  run passed 13 tests in 1.636 seconds.
- Before numeric fix, independent direct probes raised Overflow for NUM and INT,
  and returned True for whitespace/underscore spellings. After fix, all four
  probes returned False. Added direct malformed-numeric and external huge-exponent
  regressions: final run passed 15 tests in 1.749 seconds. The code change landed
  while the new tests were being written; their first execution was after the fix.
- After the numeric INT/NUM contract correction, final independent suite passed
  17 tests in 2.267 seconds. The independent small [1,2,NULL] external-optimizer
  rerun also passed one case/one VM comparison in 0.1605 seconds. No independent
  pre-fix execution of this second failure was captured; coordinator's confirmed
  reproduction triggered the fix.

Temporary failure witnesses produced by the tests are checked before their
temporary directories are cleaned. Reproducible fixture-generating test code is
retained. Tests call the supplied local interpreter; binaries remain excluded
from submission.

## Remaining risks and deferred coverage

- Finite tests provide evidence, not soundness. No optimized implementation has
  been reviewed at this milestone.
- Mixed-type output columns are not suite-generated. MiniVM serializes NUM,
  large INT, STR, and DATE as overlapping JSON string encodings; fixture type
  metadata resolves ordinary comparisons, but cannot distinguish a malicious
  type-changing rewrite whose serialized strings are identical.
- Assignment order language is ambiguous. Explicit SORT/TOPK outputs are ordered;
  bare join position tuples remain conservatively ordered by VM semantics. Pure
  no-sort filter and reassignment outputs use complete-row bag comparison.
- Assignment does not define error equivalence. Erroring-original witnesses
  currently serve as optimizer rule boundaries, not positive evaluator cases.
- Relative tolerance uses symmetric max(|expected|,|actual|), with no absolute
  slack at zero; this is a documented choice where the assignment gives no exact
  formula.
- Resource-limit equivalence remains uncertain: HJOIN promises matching semantic
  errors but consumes the VM work allowance differently from NLJOIN. Dead-code
  removal can also change resource-limit failures.
- Process groups are a practical cleanup mechanism, not a security sandbox for
  intentionally escaping processes. No Windows process-control validation was
  performed on this macOS host.

After optimizer authorization, prioritize mutation/versioning, identity-index
length proofs, NULL bounds, same-destination joins, and cross-pass interaction
regressions. Keep optimizer preconditions narrower than what these finite tests
happen to exercise.
