# Independent string-cost investigation

Scope: refine the estimate used to choose between the same two documented
equivalent join algorithms. No additional semantic rewrite. Reviewer owns only
`tests/adversarial/**`; no optimizer, evaluator, shared-helper, Git, or binary
edits. No delegation. Baseline examined: commit `3155414`.

## Independent derivation before coordinator proposal

Both sides have 64 STR values: 63 empty strings and one 10000-byte string.
There are 63*63+1 = 3970 matching pairs. NLJOIN examines all 4096 pairs, but
only the long/long comparison contributes string bytes: 10000 total.

- NLJOIN total = four base costs 16 + LOAD 128 + pairs 4096 + bytes 10000 +
  output pairs 7940 = **22180 cycles**.
- HJOIN total = base 16 + LOAD 128 + rows 768 + bytes 20000 + output pairs 7940 =
  **28852 cycles**.

The previous min(mean bytes) model substitutes 156.25 for every pair's shorter
length and predicts 640000 pair-string bytes. This is 64 times the actual 10000.
The resulting +6672-cycle regression is a cost-model deficiency, not a semantic
failure: output pairs remain identical.

Relevant documentation: `docs/instructions/joins.md:19-23`, `docs/cycles.md:11`,
`docs/cycles.md:19`, and `docs/running.md:168-178`. avg_bytes is the mean among
non-NULL strings, rounded to two decimals. common lists at most eight repeated
values; nulls and distinct are separate. STR has no histogram. These are sampled
statistics, not constraints on future data.

Independent schema probes confirmed:

- Seed skew: nulls=0, distinct=2, avg=156.25, common=[[empty,63]].
- 63 NULLs + one long string: nulls=63, distinct=1, avg=10000, common=[].
- 66 empty + one one-byte string: avg=0.01, common=[[empty,66]].
- Ten repeated values: common contains only the top eight; the remaining values
  may still repeat.

## Recommended narrow refinement and assumptions

For direct LOAD columns, use a length-frequency profile: NULL count at zero
bytes, each observed common value at its UTF-8 byte length and frequency, and
unlisted rows represented by a residual mean length. Infer residual total bytes
from avg_bytes * non-NULL rows minus the known common-byte total. FILL can have
an exact constant profile. Drop profiles through filtering, slicing, gathering,
and value-changing operations; do not treat a source distribution as the
distribution after those operations. Retaining the previous scalar heuristic
there is an explicit limitation.

For matching data and exact means, replacing each residual length distribution
by its mean makes pair-byte cost an upper estimate: min(length_left,length_right)
is jointly concave. The hash byte total is determined by each side's total bytes.
This explains why partitioning out observed common values is a defensible
refinement. It does not make the remaining tail distribution known or guarantee
an optimal algorithm. Rounded averages also weaken this exact inequality.

Coordinator's subsequent candidate matches this profile design, adds Decimal
rounding intervals (+/- .005 per non-NULL value), unique-integer total-byte
recovery where possible, and keeps the original algorithm within a conservative
rounding uncertainty band. Invalid/missing profiles fall back to the scalar
model. Reviewer considers the general residual-mean heuristic reasonable for
this cost-only scope; restricting to one residual row would avoid some uncertainty
but discard useful common-value coverage. Actual enforcement review is pending.

## Executable challenges and retained limitations

`test_string_cost_model.py` invokes the optimizer command and both raw VM
algorithms. It checks source changes remain opcode-only and exact ordered output
pairs agree. Focused fixtures include NULL/NULLEQ, UTF-8 bytes, residual singletons,
truncated common lists, rounded averages, missing/inconsistent profile fields,
profile invalidation on derived columns, and stale statistics.

Important independent cases:

- 63 empty + one ASCII 1000-byte tail: NL 13180 / H 10852, favor H.
- 63 empty + one 1000-character emoji tail (4000 bytes): NL 16180 / H 16852,
  favor NL. Character count is not byte count.
- Rounded negative central residual: 198 one-byte `x` + one empty string.
  avg 0.99*199 - common bytes 198 = -0.99, within the .995 rounding allowance;
  the nonnegative residual-byte interval admits only integer 0.
- Rounded near tie: left two copies of `zzzzz`; right 977 distinct four-byte
  strings and 23 distinct five-byte strings. True byte total 4023 is summarized by
  avg 4.02, central total 4020. Point estimates favor NL by 2, but actual totals
  favor H by 1: NL 11064 / H 11063. Previous code changes an initial H to NL;
  the proposed rounding guard should retain either initial algorithm.
- Residual holdout: eight distinct one-byte values A..H repeated four times each,
  then 31 distinct one-byte singletons and one 10000-byte singleton on each side.
  common has eight entries, distinct=40, avg=157.23. Observed NL 18655 / H 21358,
  160 matching pairs. A residual mean bucket still chooses H, retaining a
  **2703-cycle matching-statistics regret**. Previous code also chooses H;
  this is an unchanged model limitation, not a new semantic defect.
- Stale profile: statistics from the seed skew, actual values 64 copies of `x`
  per side. Refined profile selects NL even when starting from H; expected actual
  NL 16528 / H 9232. This **7296-cycle regression** illustrates distribution drift;
  the column declarations and all constraints still hold.

## Commands and chronology

```
python3 -m unittest discover -s tests/adversarial -p test_string_cost_model.py -v
```

Before implementation: first nine methods ran in 2.240 seconds, four expected-red
cost-choice assertions. Added the independently derived rounding near-tie fixture;
ten methods ran in 2.358 seconds, five expected-red assertions/subtests (seed skew,
NULL skew, emoji bytes, stale-profile choice, rounding guard). Other checks passed.
These are baseline model deficiencies, not reported semantic failures. Candidate
implementation review, corrected expectations if needed, and final measurements
will be appended after code is ready.

## Implementation review and final results

Reviewer independently inspected the candidate implementation and found these
proposed boundaries enforced:

- Profiles are attached to direct LOAD estimates and constant STR literals used
  by FILL. Register replacement replaces the profile too.
- NULL contributes zero-byte mass. Common strings use UTF-8 encoding lengths;
  counts, duplicate values, at-most-eight entries, and available distinct-count
  consistency are checked. Missing required counts or inconsistent profile data
  use the scalar fallback. If common is absent, it is treated as an empty list,
  leaving a residual-mean estimate rather than inventing common values.
- Decimal rounding intervals recover a unique integer residual total when
  possible. Otherwise the residual mean carries rounding slack. Selection keeps
  the original algorithm within its rounding margin.
- GATHER/SLICE explicitly remove the profile. Element-wise/string instructions
  construct a new estimate without a profile. They can retain the prior scalar
  mean as a heuristic, which is not a claim that the distribution survived.
- Source emission still changes only the recognized join opcode. Cost statistics
  establish no semantic rewrite preconditions and no assumption about future rows.

Focused post-change command above: **10 tests passed in 2.787 seconds**. No
expectations needed changing after implementation. Seed skew now chooses NLJOIN
(22180 cycles rather than HJOIN 28852); NULL skew without NULLEQ chooses NLJOIN
(14242 rather than 20914); ASCII/emoji near-threshold choices use byte costs;
the rounded near tie retains either original algorithm. Every selected/raw
execution checked in these fixtures has identical exact ordered output pairs.

Final combined command:

```
python3 -m unittest discover -s tests/adversarial -v
```

**41 tests passed in 7.944 seconds**. This includes all preceding evaluator,
semantic, lexical, and join regressions plus the ten focused cost methods.
No new semantic failure is confirmed. These runs provide finite evidence; they
do not prove soundness or optimal algorithm selection.

The residual-tail holdout still chooses HJOIN 21358 versus NLJOIN 18655, a retained
2703-cycle matching-statistics regret. Stale profiles still select NLJOIN 16528
versus HJOIN 9232 in the retained distribution-drift fixture, a 7296-cycle regret.
They are expressly retained model limitations, not removed from the report after
the seed case improves. The coordinator separately measures the unchanged fixed
19-workload set and always-H/always-NL policies; this review does not substitute
its new focused cases into that fixed comparison.

## Remaining risks and deferred work

- Rounding slack bounds only average-reporting error, not residual distribution
  shape, unknown correlations after derived operations, or stale statistics.
- A maximum-eight common list can hide many repeated values. distinct counts
  do not recover their length distribution, and unlisted values need not be
  singletons. Even a tail composed only of singletons can have severe length skew.
- Profile-drop scalar estimates may be inaccurate after value-changing/filtering
  operations; this milestone deliberately avoids a larger distribution analysis.
- No new claim about resource-limit error equivalence: the prior work-accounting
  ambiguity remains. Finite passing tests do not establish behavior at all limits.
- With more time, evaluate length histograms collected by a separate estimator,
  bounds for unknown tails, and a fixed broader holdout family before expanding
  propagation. Existing STR schema files do not provide length histograms.
