# Independent join cost-model evaluation

Scope: compare the same eight supplied examples and eleven existing targeted workloads under current selection, always-NL and always-H. No optimizer or benchmark module imports, optimizer edits, Git operations, shared-file edits or delegation. The fixed corpus was copied into independent fixtures in `test_join_cost_model.py`; fresh workloads for model assumptions will be labeled holdouts separately. Default evaluator stays26cases/70execution pairs.

## Before refinement

Reference code: coordinator-designated3155414. Owned snapshot: `cost-policy-baseline.json`. Every forced policy is an actual executable accepting program/schema arguments and emitting a program. The test preserves every source byte except eligible LF-anchored join opcodes, including operands, NULLEQ flags, spacing and comments. Each emitted program is run using MiniVM and its entire result width and ordered rows compared with original execution. Schema files remain frozen for each workload; stale-stat workloads deliberately use a schema derived from alternative data with the same table declarations.

For all11 simple join workloads, raw VM cycles were independently checked against `docs/cycles.md`: four instruction bases total16, LOAD values total L+R, output pairs cost2 each, then NL costs `sum(1+min(UTF8bytes(left),UTF8bytes(right)))` over all pairs; H costs `sum(6+UTF8bytes(key))` over all rows. NULL has zero string bytes. No optimizer estimates enter these calculations.

Observed aggregate cycles on the exact same19 inputs:

| Policy | Cycles |
|---|---:|
| Current3155414 selection |112833|
| Always NLJOIN |449799|
| Always HJOIN |137963|

These totals describe this fixed corpus, not general superiority. The matching-stat STR-skew case confirms a selection-model error: NL22180 versus H28852, while current selection chooses H. Stale-stat regressions and missing-estimate unchanged cases are preserved in the raw JSON rather than excluded.

Commands/results:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -p test_join_cost_model.py -v`:3tests passed3.867s.
- Independent `measure_suite()` invocation wrote the19-input snapshot with selected/NL/H cycles and selected opcode lists.
- Cross-checking the owned JSON against `records/join-selection/workloads.json` found exact agreement on raw NL/H and selected cycles for all11 existing targeted workloads.
- Actual MiniVM `--schema` probing confirmed NULLs are excluded from `common` and `avg_bytes` averages only non-NULL STRs; repeated NULL counts appear separately in `nulls`. A63-NULL-plus-one-long-STR sample has `nulls=63`, `avg_bytes=10000`, `common=[]`.

## Proposed refinement under investigation

Coordinator proposal: direct-LOAD STR profile with NULL zero-byte mass, up to8common-value UTF8 lengths/counts, and remaining non-NULL count at an inferred residual mean using the rounded non-NULL `avg_bytes`. Pair costs use cross-products of these at-most10buckets; H costs use the weighted mean. Validate consistency; malformed/missing profiles fall back to the prior average model. Drop profiles after functions/selections that change value/frequency distributions. The residual point mass is explicitly a heuristic and cannot recover arbitrary tail distributions from rounded means.

Refinement-specific tests and post-change results will be recorded after the coordinator implementation is ready. No unexecuted test outcome is claimed here.

## Refinement verification and measured comparison

After the coordinator's ready signal, all 57 then-current evaluator tests passed in 18.217 seconds. The public `./evaluate ./optimize` completed the unchanged 26 cases / 70 execution pairs: wall 4.696305167 seconds, optimizer subprocesses 2.278459583 seconds, paired VM execution 1.388644377 seconds. The CLI run overlapped the test suite, so these are observed timings rather than an isolated performance benchmark.

The same-19 post-refinement snapshot is `cost-policy-refined.json` (includes a SHA-256 of the optimizer source for identification, without importing it):

| Policy | Before | Refined |
|---|---:|---:|
| Selected | 112833 | 106161 |
| Always NLJOIN | 449799 | 449799 |
| Always HJOIN | 137963 | 137963 |

Exactly one of these 19 selected-program measurements improved: `string_skew_matching_stats`, 28852 to 22180, saving 6672 cycles. The other 18 cases were unchanged; none regressed relative to the saved baseline on this fixed corpus. The stale-large/tiny and missing-stat limitations remain, and the source-program results were identical under all three policies.

The proposal was implemented with all-row scalar means, validated direct-LOAD length profiles, Decimal rounding intervals, integer byte-total recovery where unique, a cost uncertainty band otherwise, profile invalidation after derived transformations, and exact literal FILL metadata. Tests use only the public optimizer interface and MiniVM; no optimizer implementation inspection or import supplied expected answers.

## Separate holdouts and remaining model limitations

`cost-profile-holdouts.json` records additional assumptions outside the original 19-input comparison, with complete rows checked against original MiniVM execution:

| Holdout | Selected | Raw NL | Raw H |
|---|---:|---:|---:|
| 63 NULLs plus long singleton | NL 14242 | 14242 | 20914 |
| Same, NULLEQ | NL 22180 | 22180 | 28852 |
| Full common UTF-8 distribution | H 268 | 272 | 268 |
| Singleton tail, rounded mean 4.12 / true bytes 66 | NL 822 | 822 | 824 |
| Homogeneous four-value residual tail | H 28120 | 51448 | 28120 |
| Complete common values, rounded average | H 172 | 192 | 172 |
| Derived RTRIM profile discarded | H 68988 | 62316 | 68988 |
| Derived SLICE profile discarded | H 28988 | 22316 | 28988 |
| Derived GATHER profile discarded | H 29124 | 22452 | 29124 |
| Ambiguous integer tail, keep original H | H 63768 | 63766 | 63768 |
| Literal FILL uses UTF-8 bytes | H 168 | 184 | 168 |

The derived examples intentionally expose where conservative profile invalidation leaves the scalar model choosing a more expensive algorithm. These are algorithm regrets on these separate holdouts; no pre-refinement measurement was captured for them, so they are not claimed as newly introduced regressions. The ambiguous-tail example preserves the original algorithm within the declared uncertainty band, including its two-cycle regret when the source uses HJOIN.

Additional public-interface tests reject malformed/inconsistent common lists to the scalar fallback, exercise missing profiles, preserve source operands/flags with malformed numerical estimates, and verify no optimizer crash. They include wrong types, overcounts, duplicate values, nonintegral/boolean counts, zero/negative counts, absent common lists, invalid row/null counts and invalid average bytes. No fixture treats those statistics as correctness constraints.

After the initial full 57-test run, two explicit tests were added and passed individually: ambiguous 128-row tail totals permit 14850 or 14851 bytes and retain either original opcode near a cost tie (0.348 seconds); UTF-8 literal FILL selects HJOIN (0.127 seconds). A consolidated cost-module run follows below. The finite corpus does not establish universal cost optimality or soundness; the reviewer separately investigates truncated-common-list heterogeneous tails.

Consolidated command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -p test_join_cost_model.py -v` ran all 13 cost-policy/profile test methods, including the two added holdouts, and passed in 9.227 seconds. Together with the preceding full-suite run, all current 59 evaluator test methods have been exercised successfully; this is not presented as a single 59-test timed run. No further evaluator source changes or optimizer changes were made by this agent.

## Final model choice: simple active policy; profile model archived

The coordinator chose the simpler3155414 join model for the active pipeline. The exact experimental profile implementation is retained as executable `experiments/profile_optimizer.py`; its SHA-256 matches the optimizer hash in this agent's saved `cost-policy-refined.json`. The profile tests now invoke that archived executable through its original two-argument interface. Active join-only checks invoke `./optimize --joins-only PROGRAM SCHEMA`, isolating join selection from the later dead-code pass. Required public `./optimize PROGRAM SCHEMA` remains the complete pipeline. No test was dropped to make the simpler model pass.

This agent independently recomputed all stored policy measurements, including the favorable evidence for the archived model:

| Corpus | Cases | Simple model | Profile model | Profile minus simple |
|---|---:|---:|---:|---:|
| Original fixed corpus |19|112833|106161|-6672|
| Additional stale-profile case alone |1|9232|16528|+7296|
| Original fixed corpus plus that stale case |20|122065|122689|+624|
| Matching-stat profile holdouts |9|219888|205871|-14017|
| All profile holdouts, including stale case |10|229120|222399|-6721|
| Original fixed corpus plus all holdouts |29|341953|328560|-13393|

The20-case result does not demonstrate that the simpler model is generally faster: all29 cases favor the profile model. Neither aggregate establishes expected performance without representative workload frequencies. The reason to freeze the simpler active model is its smaller implementation/proof surface, no improvement on the eight supplied examples, sensitivity to stale statistics and unmodeled heterogeneous tails, and the assignment's limited scope. The archived model remains a reproducible experiment with measured benefits and limits.

After adapting tests to separate active join-only selection, the archived profile experiment and the complete DCE pipeline, the full evaluator-owned suite ran73 tests and passed in24.720 seconds. The public evaluator completed26 cases/70 execution pairs on the active full pipeline without defects. Detailed DCE evidence is in `DCE_REPORT.md`.

The subsequent DCE lifetime correction adds two lightweight structural regressions without changing either join model. Final post-guard evaluator-owned verification ran75 tests, all passing in24.370 seconds; actual public evaluator still completed26/70. See `DCE_REPORT.md` for the confirmed resource failure, first-definition restriction and final CLI timings.
