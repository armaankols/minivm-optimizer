# Fresh review of frozen MiniVM implementation

Reviewed implementation: 49c704877deed17b45b3e360f1f6f683b0db5b90.
Checkout HEAD: fc300d2 (documentation preparation).
Repository: /Users/armaankolsawala/Downloads/Assessment/aim-takehome.

The checkout was clean before review. The requested command
`git diff 49c7048..HEAD -- '*.py' optimize evaluate` returned no changes.
No implementation or tracked documentation was edited in this review.

## Findings

### [P2] Restore the pristine program before executing the baseline oracle

Location: evaluator.py:407; optimizer invocation at evaluator.py:378.

The evaluator passes its baseline program path to the optimizer, then later runs
that same path as the original without restoring its contents. An in-place
optimizer can therefore overwrite the oracle's input and print its changed source.
A wrong rewrite then gets compared with itself.

Reproducer: `inplace-wrong-optimizer` in this directory changes `DIV b,a,3` to
`DIV b,a,2`, writes that text back to the program argument and prints it. Running
`./evaluate /Users/armaankolsawala/Downloads/Assessment/review-49c7048/inplace-wrong-optimizer` exits 0 after all
26 cases / 70 executions. This is an actual numeric-result change in the existing
numeric_values fixture. The control `nonmutating-wrong-optimizer` makes exactly
the same stdout rewrite but leaves its input alone; the evaluator exits 1 on
numeric_values with an unordered-row mismatch. These are standard public CLI
runs against the original interpreter, with no evaluator imports or patches.

Suggested correction: restore `case.program` after the optimizer returns, before
using it as an oracle; alternatively execute a pristine baseline copy that was
not handed to the optimizer. Add the in-place wrong rewrite as a regression.
This is about ordinary in-place input mutation, not a claim to sandbox malicious
same-user processes.

Raw results: input-mutation-witness.json. Both executable reproducer scripts are
text files in this directory.

### [P2] Enforce the VM file-size limit after expanding a join opcode

Location: optimizer.py:194-196; final emission at optimizer.py:274.

Changing HJOIN to NLJOIN adds a byte. There is no final source-byte-size guard.
A valid program at the VM's 4 MiB limit can consequently be emitted above the
limit, introducing an error in a successful original program.

The reproduced original consists of:

```
LOAD x,t.x
HJOIN l,r,x,x
OUT l,r
```

followed by one comment padding the UTF-8 file to exactly 4,194,304 bytes. Table t
has a single INT column x and row [1]; schema is obtained using the supplied VM's
--schema. Both join results are live, so DCE does not offset the expansion.

Original: exit 0, rows [[0,0]], cycles 27.
Candidate: 4,194,305 bytes, exit 1, `larger than 4 MB`.
The optimizer exits 0 in about 0.09 seconds and selects NLJOIN.

This witness starts with a successful original; it does not depend on the
underspecified equivalence of failing originals or differing join work accounting.
Suggested correction: check the final encoded byte length and fall back to the
original valid source if the transformed source exceeds the VM limit. Retain a
boundary regression for an HJOIN-to-NLJOIN expansion.

Reproducer: `python3 /Users/armaankolsawala/Downloads/Assessment/review-49c7048/boundaries.py`.
Raw results: source-size-witness.json. Program/data/schema fixtures are retained
as at-limit.mini, candidate.mini, data.json and schema.json.

## Verification results

- Original assignment PDF was extracted and visually inspected. Its SHA-256 is
  00f086154b7de990a61d3cd243710964ecee5be418eec12812d07eae919bf877, matching
  docs/assignment.md. No requirements transcription discrepancy found.
- Read optimizer.py, sorted_order.py, dead_code.py, evaluator.py; checked the
  relevant original language, execution, columns, strings, dates, grouping,
  sorting and join documentation, implementation proofs and contract.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v`:
  75 tests passed, 25.867 seconds.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v`:
  75 tests passed, 23.730 seconds.
- `./evaluate ./optimize`: exit 0; 26 cases / 70 executions; 5.025 seconds.
- `tools/verify_baseline.py`: identity and current optimizer accepted; all five
  deliberate mutants rejected with witnesses. Receipt: cli-checks.json.
- `tools/benchmark_sorted.py`: 39 exact-output checks passed; six improvements,
  33 unchanged relative to the pipeline with sorted-order disabled. Receipt:
  benchmark.json.
- `tools/benchmark.py ./optimize`: original total 60,363, candidate total 59,121;
  candidate cycles 12766,3527,8562,18442,5518,6338,2444,1524. Receipt: examples.json.
- Default lifetime replay: original and current successful, exactly equal
  results/cycles. Receipt: lifetime.json. Unsafe optional variant was not run.

## Limits and remaining items

This is a finite review, not a proof. Existing declared caveats about join cost
regressions, VM type-tag ambiguity and resource/work limits remain. The 10-second
candidate-VM timeout is classified as an optimizer defect even though the
assignment imposes no separate VM execution-time limit; I did not reproduce a
valid equivalent candidate that exceeds it on these small fixtures, so this is
retained as an existing policy concern rather than an additional witnessed finding.
No network publication check or second-platform execution was performed. Pending
user-supplied model/usage metadata and publication confirmation remain as recorded
in SUBMISSION_CHECKLIST.md.

Review artifacts are saved beside the checkout, outside the Git repository. Public evaluator
mutant runs also write ignored .evaluation-failures witnesses as designed.
