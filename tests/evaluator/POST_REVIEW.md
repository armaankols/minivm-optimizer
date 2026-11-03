# Post-review evaluator oracle correction

Scope: fix only the in-place optimizer-input mutation finding in `/Users/armaankolsawala/Downloads/Assessment/review-49c7048/REVIEW.md`. The evaluator specialist changed `evaluator.py` and added `test_input_mutation.py`; no optimizer implementation, shared helpers, Git state or supplied review files were modified. The coordinator owns the separate source-size finding.

## Reproduced before changing code

Both commands used the supplied external executable scripts and the ordinary public interface:

- `PYTHONDONTWRITEBYTECODE=1 ./evaluate /Users/armaankolsawala/Downloads/Assessment/review-49c7048/inplace-wrong-optimizer` incorrectly exited0 after26 cases/70 executions (reported wall3.723221625 seconds). Its wrong DIV-by-2 rewrite was compared with its own rewritten input file instead of the pristine DIV-by-3 source.
- The same command with `nonmutating-wrong-optimizer` correctly exited1 on `numeric_values`, with an unordered-row mismatch and a retained witness.

The only difference between the two scripts is writing the rewritten text back to the program argument. This confirms an oracle isolation bug rather than any issue in result tolerance or optimizer internals.

## Correction and argument

Each case now gets a fresh temporary directory. The optimizer receives its own `optimizer-input.mini`, initially populated from the authoritative in-memory `case.program`. After the optimizer subprocess finishes and its descendants are reaped, the evaluator creates a separate `original.mini` from `case.program`; this baseline path was never handed to the optimizer. Every alternative dataset executes that pristine baseline. Candidate execution still uses only stdout from the optimizer.

Consequently, ordinary rewriting, atomic replacement, removal or permission changes to the optimizer's input cannot change the baseline source. Fresh per-case paths also prevent a read-only input left by one invocation from blocking the next case. Failure fixtures continue to write `case.program` as `original.mini`, so their source agrees with the program that produced the saved expected result.

This isolates ordinary command input mutation. It is not a filesystem sandbox or a security claim against malicious same-user processes. The CLI, comparison rules, time limits, default26-case/70-execution corpus and optimizer invocation count are unchanged.

## Retained regressions and observed results

`test_input_mutation.py` contains four methods using executable subprocesses:

1. Public CLI rejects both the in-place wrong rewrite and its nonmutating control. Each retained witness has pristine DIV-by-3 source, wrong DIV-by-2 candidate, and expected/actual JSON that exactly matches independent MiniVM replay of those files.
2. Public CLI accepts an identity optimizer that writes its input in place and leaves it mode0400, completing all26 cases/70 executions.
3. An identity optimizer may unlink its input after reading it; two cases and all their datasets still complete.
4. A wrong optimizer may atomically replace its input with a read-only file; it is still rejected and its failure fixture remains pristine.

Commands/results after the correction:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -p test_input_mutation.py -v`:4 tests passed in5.893 seconds.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -p test_evaluator.py -v`:the existing31 harness tests passed in6.044 seconds, including ordinary identity acceptance and known-wrong rejection.
- The two original supplied public CLI commands were rerun: both now exit1 on `numeric_values` with the same unordered-row mismatch. Ignored default witness directories were retained for both runs.

The coordinator and independent reviewer were notified when the minimal fix was ready. Full integration results and the reviewer's independently owned mutation tests are recorded by their respective owners; the results above do not claim an unexecuted full-suite run.

Machine-readable public before/after receipts and verified retained witness paths are saved in `post-review-cli.json`. The in-place false acceptance produced no failure directory, as expected; the control-before and both after-fix rejection directories exist and contain their complete fixtures.

An additional actual `PYTHONDONTWRITEBYTECODE=1 ./evaluate ./optimize` after the correction exited0 with26 cases/70 executions: observed wall4.791835292 seconds, optimizer subprocesses2.211589789 seconds and paired VM1.461685003 seconds. It overlapped other checks. The coordinator independently reported full-suite integration passing79 evaluator tests and83 adversarial tests, plus identity/current acceptance and five known-wrong rejections; those are coordinator results, not additional runs claimed by this agent.

Edits are complete for this focused fix: `evaluator.py`, `tests/evaluator/test_input_mutation.py`, `tests/evaluator/POST_REVIEW.md` and `tests/evaluator/post-review-cli.json`. No further features or source changes are planned.
