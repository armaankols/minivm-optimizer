# Independent proven-total dead-code checks

Owner: evaluator specialist. Scope: black-box required two-argument optimizer interface; no optimizer implementation imports, source edits, Git operations, shared-file edits or delegation. Existing join-stage source/cycle tests now use `--joins-only`; archived profile-model tests invoke `experiments/profile_optimizer.py`. The public evaluator corpus remains26 cases/70 execution pairs.

## Contract and independent oracle

`test_dce_optimizer.py` runs original and emitted programs with MiniVM. Each program is optimized once using a schema frozen from its first valid dataset, then tested on alternatives with the same declarations, including all-NULL/non-NULL and empty/nonempty variations. Result width, complete ordered rows, duplicate output columns, row multiplicity, value associations and VM success/error status must agree.

Positive removal expectations follow only the coordinator's stated whitelist and documented VM behavior: a LOAD of a guaranteed declared column; IOTA/SLICE/ISNULL on known column registers with valid slice counts; STR-only UPPER/RTRIM/TRIM/LEN/NULLIFE/LEFT/SUBSTR with valid literal counts/start; DATE-only YEAR/MONTH/DAY/DOW. Source type facts derive from guaranteed table declarations and valid instruction postconditions, never statistical row counts, observed NULL frequencies or extrema.

A final additional precondition requires every removable destination to be a textual first definition. Any previous write, including either output of a join, forbids deletion of a later overwrite. Semantic totality alone does not establish safe deletion because overwrites also release old register values.

No removal is required for FILL, GATHER, TRUNC, arithmetic, joins, sorting or grouping. Their results may be dead while their errors remain observable. Tests require these operations and their needed inputs to remain when applicable. Unknown opcode/syntax requires the whole DCE pass to preserve the join-stage source. The tests compare DCE emission with join-only emission and allow only blank/comment replacements for removed instructions, preserving LF count, CRLF markers and final newline state.

Documentation supporting the tests: `docs/instructions/README.md:20–30` requires correct register kind, matching operand lengths and row-sensitive NULL/type behavior; `columns.md:17–85` defines column operations, bounds and OUT shape; `arithmetic.md:25–55` defines overflow/division errors; `dates.md:42` bounds DATEADD; `grouping.md:51,71` specifies empty GALL and NULL GFIRST.

## Retained cases

The initial14 independent test methods cover the following cases; two additional lifetime-guard regressions are recorded below:

- Every whitelist operation as unused leaf work, followed by elimination of its now-unused valid LOAD dependencies.
- Removal of a dead first LOAD definition before a live overwrite, plus self-reassignment using a previous register version. Later dead overwrites are retained by the final lifetime guard.
- Dead DIV0 and invalid arithmetic/string/conditional types under all-NULL masks, followed by a non-NULL dataset that reveals the original error.
- Cross-table length mismatch even when the frozen statistics initially describe equal lengths.
- INT128 multiplication overflow and DATEADD beyond year9999.
- Invalidation of an old STR fact after an unmodeled FILL or a new INT LOAD.
- Invalidation of a column fact when GROUP overwrites the register; IOTA/ISNULL/SLICE must preserve the resulting group/column-kind errors.
- Out-of-range GATHER, plus GFIRST of an empty GALL producing a NULL index.
- Missing columns, negative counts and invalid SUBSTR start.
- OUT order, STR/INT structure, duplicate operands and repeated rows.
- A retained join whose two destinations alias each other and an input; its prewrite source operands remain live.
- Unknown opcodes/operand syntax, comments, CRLF and absent final newline.

The default public evaluator tests still exercise an independent identity executable and deliberately incorrect optimizers through their actual command interfaces. They test comparator, subprocess, malformed-output, timeout and deadline behavior; they do not import the submitted optimizer.

## Commands and observed results

1. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -p test_dce_optimizer.py -v`:14 tests passed in6.026 seconds. No confirmed DCE failure was found by this agent.
2. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v`:73 tests passed in24.720 seconds, including all earlier harness/join/archive-profile tests and all14 new DCE methods.
3. Actual `PYTHONDONTWRITEBYTECODE=1 ./evaluate ./optimize`: exit0;26 cases/70 execution pairs; observed wall4.560126667 seconds, optimizer subprocesses2.198256793 seconds, paired VM execution1.363382086 seconds. This ran concurrently with the full test suite and is not an isolated benchmark timing.
4. Deterministic positive fixture saved in `dce-positive.json`, including full source, optimized source and input datasets. Unused STR UPPER/LEN/IOTA/SLICE and their LOAD are removed, leaving LOAD/OUT. Cycles: populated78→11, empty28→8, all-NULL34→9. These are explicitly positive fixtures; representative example benchmarks and unchanged cases are the coordinator's separate measurements.

## Limits

Passing tests supplies evidence, not a proof. Tests preserve semantic errors; equivalence of VM resource-limit failures remains a documented ambiguity because removing total work can avoid aggregate register/work limits. No deletion of joins or other potentially unbounded producers is assumed. Test programs exercise the declared small whitelist rather than trying to establish general DCE safety for every opcode or arbitrary malformed source. The public evaluator's standard corpus uses successful baselines; these standalone DCE tests add direct original/candidate execution for semantic-error witnesses without changing its26/70 interface corpus.

## Confirmed register-lifetime failure and final guard

The coordinator reproduced a genuine before-fix failure, fully retained in `records/dce/lifetime-before-fix.json`: eight fresh 2000-by-2000 constant-key HJOINs each write two4-million-position columns, then LOAD overwrites both destinations with small columns. Original execution succeeds in the recorded run. Removing those apparently dead, semantically total LOADs leaves old large values resident; the candidate fails at line23 with more than64000000 register values. This is an introduced failure for a successful original, not merely the ambiguity about optimizing an already resource-limited run.

The fix restricts deletion to textual first definitions. The definition-history set includes all writes and both outputs of a join, independently of liveness or whether an earlier defining instruction is later removed. Later overwrites remain even when their values are dead and their operation is semantically total. This conservative restriction prevents deletion from extending a previously stored value's lifetime.

This agent reviewed the saved complete program/candidate and coordinator results. At the coordinator's explicit request, it did not duplicate the approximately1GB resource probe. Instead, two lightweight retained regressions were added: the same eight-join/16-overwrite structure on tiny data must preserve every overwrite LOAD; an unused UPPER/LEN/IOTA/SLICE self-write chain must also remain. The old positive test was renamed to clarify that it deletes a dead **first definition** before a live overwrite, which remains permitted. All earlier semantic-error and alias checks remain.

Post-guard focused command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -p test_dce_optimizer.py -v`:16 tests passed in5.707 seconds. Earlier73-test timings above predate the guard and are superseded for final verification by the results below.

Final post-guard verification:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v`: all75 tests passed in24.370 seconds. This includes all16 DCE tests plus the prior harness, isolated-join and archived-profile tests; no earlier tests were removed.
- Actual `PYTHONDONTWRITEBYTECODE=1 ./evaluate ./optimize`: exit0;26 cases/70 execution pairs; observed wall4.55707875 seconds, optimizer subprocesses2.201799206 seconds, paired VM1.337508624 seconds. It ran concurrently with the full test suite. These final results supersede the pre-guard full-suite/CLI results above.
- An additional ad hoc syntax probe verified that invalid destinations TRUE, NULL, ASC and `1bad` preserve original MiniVM failure and unchanged program text. OUT is permitted as a register name by the actual VM; its unused first LOAD was removed without changing success. No additional failure was found.

No full resource-heavy probe was duplicated by this agent. The coordinator owns the saved before/after resource execution; these final tests independently enforce its structural guard on small data. No further edits are planned unless a new confirmed finding requires them.
