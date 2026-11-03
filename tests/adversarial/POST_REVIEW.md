# Independent follow-up to fresh review 49c7048

Read the supplied `review-49c7048/REVIEW.md` and reproducer scripts before testing.
Scope: reproduce the two reported failures, retain black-box regressions, inspect
the assigned fixes. Reviewer edits only `tests/adversarial/**`; no optimizer,
evaluator, shared-helper, Git, or binary edits and no delegation.

## Confirmed before-fix findings

Ran the supplied public commands independently before the fixes:

```
python3 /Users/armaankolsawala/Downloads/Assessment/review-49c7048/boundaries.py
./evaluate /Users/armaankolsawala/Downloads/Assessment/review-49c7048/inplace-wrong-optimizer
./evaluate /Users/armaankolsawala/Downloads/Assessment/review-49c7048/nonmutating-wrong-optimizer
```

- Byte expansion reproduced: input 4194304 bytes, output 4194305 bytes. Optimizer
  exits 0 in 0.115969167 seconds, changing HJOIN to NLJOIN. Original VM exits 0,
  rows [[0,0]], cycles 27; candidate exits 1 with `larger than 4 MB` and no result.
  This introduces failure on a successful original, not an underspecified
  failing-original case.
- In-place wrong DIV-by-2 rewrite was falsely accepted: public evaluator exits 0,
  26 cases / 70 executions, wall 3.438111375 seconds. The same stdout rewrite
  without input mutation correctly exits 1 on numeric_values with an unordered
  row mismatch and a retained failure witness.
- Added independent external-optimizer oracle tests before the evaluator fix:
  three methods ran in 0.839 seconds. Equivalent in-place comment normalization
  passed; wrong in-place rewrite was falsely accepted (test failure); corrupting
  the input but emitting correct original stdout was falsely rejected (test
  error). Both incorrect outcomes follow from running the optimizer-modified
  program as the baseline oracle. These are retained in
  `test_oracle_input_mutation.py`.

## Final source-byte guard review and tests

Coordinator fixed the active optimizer before these new boundary tests first ran.
Reviewer inspected final emission: encode selected source to UTF-8 after join,
sorted-order and DCE passes finish; if encoded length exceeds 4*1024*1024, emit
the cached original bytes instead. The guard is shared by default,
`--joins-only`, and `--no-sorted-order`. Equality at the limit is permitted.

Command:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -p test_source_byte_limit.py -v
```

**Five methods passed in 1.654 seconds.** They execute original/candidate MiniVM
programs and cover exact-limit identity fallback, a one-byte-smaller input whose
expanded candidate is exactly at the limit, emoji UTF-8 comments measured in
bytes rather than characters, all three active modes, and a case where DCE frees
enough room after join expansion so the final candidate remains applicable.
Normal small HJOIN -> NLJOIN still runs and reduces 27 cycles to 16.

All 4 MiB programs are generated inside temporary directories. No padded source
or binary fixture is added to the repository. The archived profile experiment is
historical code, not the active optimizer covered by this fix.

## Pristine-oracle fix review and post-fix replay

Reviewer independently inspected `evaluate()`: every case now gets a fresh
directory; only `optimizer-input.mini` is passed to the optimizer. After the
optimizer subprocess has exited and its process group has been reaped, the
evaluator writes `case.program` to separate `original.mini` and uses that path
for every baseline VM execution. Candidate stdout is written independently.
The cached pristine source also supplies saved failure witnesses. Fresh case
paths avoid carrying input deletion or permission changes into the next case.

Command:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -p test_oracle_input_mutation.py -v
```

**All three methods passed in 0.711 seconds.** Wrong in-place stdout is rejected
with differing expected/actual rows and a pristine saved original; equivalent
in-place comment normalization is accepted; corrupting the input while printing
correct original stdout is accepted. Both acceptance controls execute two
alternative datasets under the same frozen schema.

Independently replayed the supplied public in-place and nonmutating wrong
optimizer scripts after the fix. Both now exit 1 on numeric_values with the same
unordered-row mismatch and retained witnesses. This corrects both the false
accept and the related false reject observed before the fix. No evaluator code
was edited by this reviewer.

## Outcome and limits

Both supplied findings were independently reproduced before fixes and verified
afterward. Eight new owned regression methods pass across the two focused
modules. The coordinator runs the final full regression suites, identity/current
CLI checks, deliberate mutants and benchmark comparisons; those are not claimed
as independent executions by this reviewer. No new witnessed failure remains
in this follow-up review.

The oracle change protects against ordinary optimizer mutation of its input
argument; it is not a sandbox for malicious same-user processes. The existing
10-second candidate-VM policy concern remains unconfirmed by a valid slow-candidate
witness and was not expanded in this fix. Historical profile experiments and
other previously documented limitations remain explicitly separate from the
active optimizer. Finite passing tests do not prove universal soundness.
