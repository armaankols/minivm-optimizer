# Evaluator baseline implementation record

Owner: evaluator specialist. Scope authorized: evaluator baseline only; optimizer remains untouched by this agent. No Git operations or nested delegation performed.

## Implemented interface and policies

- `./evaluate OPTIMIZER` invokes the supplied executable with program/schema file arguments. Exit 0 means the finite suite finished without a discovered defect; exit 1 identifies a witnessed optimizer defect; exit 2 reports usage or incomplete evaluation/infrastructure failure.
- `evaluator.py` imports no optimizer implementation. It supplies 26 independent program cases and 70 baseline/candidate execution pairs: all eight provided examples on original and empty data, plus seeded operator and constraint fixtures. Seeds are 1729 and 8675309.
- One schema is frozen per program before invoking the optimizer. The same emitted program runs on alternative datasets whose declarations are verified equal, excluding statistics. MiniVM `--schema` validates every dataset's actual declared constraints.
- The comparator uses homogeneous output-column type metadata, complete rows and multiplicity. Ordered fixtures compare positional rows; unordered fixtures use maximum bipartite matching under numeric tolerance, with a type-tagged exact Counter fast path. It does not sort or compare columns independently. STR/DATE are exact; BOOL uses exact type; INT/NUM use Decimal with symmetric relative error <=1e-6 times the larger magnitude. Zero has no absolute slack.
- Numeric-looking strings are interpreted using fixture metadata, never text heuristics. Mixed-type output columns are deferred. VM JSON itself cannot distinguish a NUM/large INT and a STR with an identical serialization; this limits detectable type-only changes even with metadata.
- Ordered fixture policy: explicit SORT/TOPK selection/order and directly exposed join position sequences are checked in order. Filter and register-reassignment value outputs are unordered. This conservative choice is documented because the assignment does not formally define what counts as specifying order.
- Subprocesses use argv arrays (paths with spaces supported), bounded stdout/stderr, timeouts and POSIX process groups. Descendants are killed/reaped even when the parent exits while holding inherited pipes. Optimizer limit defaults to 60 seconds, VM operation limit to 10 seconds, total evaluation budget to 840 seconds, leaving 60 seconds beneath the assignment's 900-second limit. Budget exhaustion yields incomplete, never a clean pass.
- Witness directories under ignored `.evaluation-failures/` contain original/candidate programs, frozen schema, data, expected/actual results, seeds and raw streams encoded as text hex. Harness tests normally use private temporary artifact roots; the public-CLI rejection test intentionally retains its witness under the default directory.

## Commands and observed results

Before implementation, all eight supplied programs executed via `bin/minivm` and exactly matched supplied expected JSON, including cycles: 13766, 3617, 8562, 18442, 5518, 6338, 2596, 1524. First subprocess approximately 0.113 seconds and later subprocesses approximately 0.011–0.016 seconds in that measurement.

1. Created `evaluator.py`, replaced `evaluate` stub, created `tests/evaluator/test_evaluator.py`.
2. `python3 -m py_compile evaluator.py` could not write macOS's configured Python cache outside writable roots. This was an environment/cache-write failure, not a syntax result. Subsequent commands use `PYTHONDONTWRITEBYTECODE=1` and successfully import/execute the code.
3. `PYTHONDONTWRITEBYTECODE=1 ./evaluate ./optimize`: identity accepted, 26 cases/70 executions, wall 2.181207542 seconds; optimizer subprocess time 0.094700751 seconds; paired VM time 1.219871084 seconds. The VM figure excludes schema validation; wall includes it.
4. `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v`: initial 24 tests passed in 4.171 seconds.
5. Reviewer identified a suspected false rejection from ordered annotations on filter/reassignment output fixtures. Corrected both to unordered before final baseline. Added schema declaration equality validation and two tests (changed-declaration rejection; actual CLI mutant rejection).
6. Same unittest command: 26 tests passed in 4.616 seconds. Actual CLI accepts an independent identity optimizer and rejects a deliberately empty-output optimizer with exit 1 and a retained witness.

Unit/interface coverage includes duplicate loss, corrupted row associations, changed column structure/order, augmenting-path numeric matching, tolerance boundary and zero, numeric-looking STR, BOOL/INT separation, NULL distinctions, wide integers, malformed VM JSON, changed numeric and NULL behavior, optimizer nonzero/invalid/empty/invalid-UTF8 output, output floods, missing executable, timeout, descendant cleanup, frozen statistics, changed schema declarations and injected short overall deadlines.

## Limits and deferred work

- Finite testing is evidence, not a soundness proof. The first milestone does not exhaust all instruction combinations, constraints or interactions.
- Baselines in this suite succeed. Semantic-error preservation is a separate adversarial concern; resource-limit failure equivalence and the assignment's error contract remain ambiguous.
- Mixed-type output columns, arbitrary-schema generation, cyclic foreign-reference generation and exhaustive boundary constraints are deferred. Constraints here combine composite keys, references, check bounds and sorted declarations; supplied examples add other declared cases.
- No statistical coverage percentages, token counts or spend are claimed. Model/reasoning settings were inherited from the coordinator; this agent has no authoritative usage telemetry.
- Process-group implementation targets the provided macOS/Linux execution environment, not Windows.

## Confirmed comparator failure and fix

Coordinator reproduced `cell_equal('1.0', '1e1000000', 'NUM')` raising raw `decimal.Overflow`, and a real candidate program emitting that STR payload caused evaluation to escape without retaining a witness. Reviewer independently confirmed the same issue for INT and accepted whitespace/underscore spellings. This was a confirmed failure, distinct from the ordering-annotation concern above.

Fixed by restricting string spellings to MiniVM's ordinary signed decimal output grammar (INT has no decimal point), bounding numeric spelling length, and catching Decimal exceptions during construction and comparison. Exponent notation, whitespace, underscores, special values and overlong spellings are rejected. Identically serialized numeric-looking STR versus numeric values remain inherently ambiguous in MiniVM JSON.

Retained direct and actual optimizer-command reproductions in `test_evaluator.py`. Final regression run after the fix: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v` ran 28 tests, all passing in 4.521 seconds. An additional identity CLI run after schema/order fixes and before this numeric fix accepted all 26 cases/70 executions in 2.173754875 seconds (optimizer 0.092594456 seconds; paired VM 1.214197999 seconds).

## Confirmed numeric-type false rejection and fix

Coordinator reproduced a valid optimizer converting stored INT32 values to NUM with `ADD y,x,0.1; SUB y,y,0.1`. For original `LOAD x,t.x; OUT x` and rows `[1], [2], [NULL]`, the candidate prints `"1.0"`, `"2.0"`, NULL and preserves numeric values for every possible stored INT32. The original comparator rejected decimal-string candidate encodings in INT fixture slots. This was a confirmed false rejection.

Fixed INT and NUM fixture slots to use one canonical decimal spelling grammar and the same relative numeric comparison; removed the candidate-integrality requirement. BOOL remains distinct and STR exact. This supersedes the earlier grammar note that INT candidate text cannot contain a decimal point. Exponent, whitespace, underscores, special values and overlong strings remain rejected. Retained both actual optimizer-command acceptance and inside/outside tolerance tests for an INT expected slot.

Post-fix validation: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v` ran 30 tests, all passing in 5.033 seconds. The actual CLI identity test again completed the full 26-case/70-execution suite.

Planning environment note: system Python lacked pypdf/pdfplumber/fitz and pdftotext was unavailable. A Swift/PDFKit extraction attempt first encountered a denied default module-cache path, then failed with conflicting SwiftBridging modules using a temporary cache. The coordinator supplied a successful independent PDFKit text extraction at `/tmp/minivm-assignment.txt`, which this agent read. These extraction failures did not change repository files or affect VM execution.

Later narrow harness correction during join selection milestone: a correct optimizer producing more than256KiB stderr diagnostics was falsely labeled defective. After reproducing it, the coordinator authorized draining/discarding excess stderr while retaining bounded capture; fatal stdout cap and time bounds remain. External noisy-identity acceptance and stdout-flood rejection are retained. Baseline test count is now31. Full join-milestone evaluator suite31+15 tests passed in8.849s; detailed chronology and commands are in `JOIN_REPORT.md`.
