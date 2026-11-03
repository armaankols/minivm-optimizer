# Fresh-review fixes and verification

Read the [supplied review](supplied-REVIEW.md) before editing. It reviewed
`49c7048`, with documentation HEAD `fc300d2`. Both P2 findings were reproduced
before fixing, independently by the original specialists. No new optimization
was introduced.

## Confirmed fixes

1. **Source-size preservation — commit `af12e15`.** A valid exact-4-MiB program
   became one byte too large when HJOIN expanded to NLJOIN. The final encoded
   candidate now falls back to original bytes when above 4,194,304 bytes. The
   guard runs after all passes and covers every mode. [Proof and evidence](SOURCE_SIZE.md).
2. **Pristine evaluator oracle.** An external optimizer editing its input could
   make a wrong division rewrite compare with itself. The evaluator now gives
   each case its own optimizer-input copy and creates a separate baseline from
   the in-memory original after the optimizer exits. VM baseline runs never use
   the path passed to the optimizer. Read-only replacements or deleted inputs do
   not contaminate later cases. Saved original source and expected output remain
   associated. This is input isolation, not a security sandbox.

The evaluator bug caused both false acceptance of wrong output and false
rejection of correct stdout when the input file was changed. Regression tests
exercise both outcomes, equivalent in-place rewrites, atomic read-only replacement,
input removal, multiple datasets and replayable pristine failure fixtures.

## Coordinator verification

| Check | Result |
|---|---|
| Evaluator suite | 79 tests passed, 32.378s |
| Adversarial suite | 83 tests passed, 27.368s |
| Public `./evaluate ./optimize` | 26 cases / 70 executions accepted, 5.967s internal wall time |
| CLI baseline verification | Independent identity/current accepted; all five deliberate mutants rejected |
| Eight supplied examples | Exact outputs preserved; 60,363 original -> 59,121 current cycles |
| Diagnostic benchmark | All 39 exact-output cases pass; 6 improve / 33 unchanged against sorted-order-disabled pipeline |
| Boundary witness | All three modes now return byte-identical original, VM success, rows [[0,0]], cycles 27 |

Full suites and CLI checks ran concurrently; wall times include process startup
and contention, and do not demonstrate a speed change. Example optimizer calls
measured roughly 85–89ms in this run. Per-program cycles remain
12766, 3527, 8562, 18442, 5518, 6338, 2444, 1524. All join holdouts remain in the
39-case collection; existing join cost regressions and combined profile tradeoff
in the [handoff](../../REVIEW_HANDOFF.md) are unchanged.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
./evaluate ./optimize
review_dir="$(mktemp -d)"
python3 tools/verify_baseline.py --output "$review_dir/cli-checks.json"
python3 tools/benchmark.py ./optimize --output "$review_dir/examples.json"
python3 tools/benchmark_sorted.py --output "$review_dir/benchmark.json"
```

The independent reviewer signed off after inspecting the pristine oracle and
rerunning three mutation tests (0.711s), including both previously wrong outcomes.
The evaluator owner separately passed four new methods (5.893s), replayed both
supplied CLI scripts and independently replayed saved expected/actual fixtures.

Raw outputs, JSON, supplied mutant scripts and retained witnesses are beside this
document. To replay the newly rejected mutants (each must exit 1):

```sh
./evaluate records/post-review/inplace-wrong-optimizer
./evaluate records/post-review/nonmutating-wrong-optimizer
```
Large boundary programs are generated in temporary directories, not committed.
Specialist follow-up reports are in `tests/evaluator/POST_REVIEW.md` and
`tests/adversarial/POST_REVIEW.md`.

## Remaining limits

Finite tests do not prove soundness. The evaluator's 10-second candidate-VM cap
remains a policy concern; the fresh reviewer did not reproduce an equivalent
candidate exceeding it. Error/resource equivalence, type-tag ambiguity and join
cost prediction caveats remain. No second-platform or new fresh-clone run was
performed for these fixes. AI model/reasoning/usage details still await the user.
GitHub DNS still fails, so publication remains user-managed and unverified here.
