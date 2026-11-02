# Join selection milestone

Only NLJOIN/HJOIN opcode selection is implemented. All other source bytes,
including operands and NULLEQ, are preserved. The implementation, preconditions,
cost model and correctness argument are in `../../docs/optimizer.md`.

## Supplied examples

| Program | Before cycles | After cycles | Saved |
|---|---:|---:|---:|
| q0001 | 13766 | 13570 | 196 |
| q0002 | 3617 | 3617 | 0 |
| q0003 | 8562 | 8562 | 0 |
| q0004 | 18442 | 18442 | 0 |
| q0005 | 5518 | 5518 | 0 |
| q0006 | 6338 | 6338 | 0 |
| q0007 | 2596 | 2596 | 0 |
| q0008 | 1524 | 1524 | 0 |
| Total | 60363 | 60167 | 196 |

Total cycle reduction: **0.3247%**. One improvement, seven unchanged, no
regressions. q0001 line31 changes HJOIN to NLJOIN. Exact full results, numeric
representations and row order agree; the benchmark also checks that only join
opcode bytes changed. All seven unchanged programs are byte-identical.

## Fixed targeted workloads

These are deterministic diagnostic workloads, not a representative aggregate
speedup claim. Both raw algorithms are executed on every case and compared to
the selected program. Data generation is retained in `tools/benchmark_joins.py`.

| Workload | Original -> chosen | Before | After | Saved |
|---|---|---:|---:|---:|
| INT 2 by 3 | H -> NL | 55 | 31 | 24 |
| INT 64 by 64 | NL -> H | 4368 | 1040 | 3328 |
| INT 12 by 12, cost tie | H -> H | 208 | 208 | 0 |
| Empty left, 32 right | H -> NL | 240 | 48 | 192 |
| Duplicates and NULL/NULLEQ | H -> NL | 93 | 59 | 34 |
| STR 32 by 32, long left/short right | H -> NL | 33264 | 2128 | 31136 |
| STR 64 by 64, similarly long keys | NL -> H | 339060 | 11516 | 327544 |
| STR skew, matching stats | NL -> H | 22180 | 28852 | -6672 |
| Estimated 64/side, actual 2/side | NL -> H | 28 | 48 | -20 |
| Estimated 2/side, actual 64/side | H -> NL | 1040 | 4368 | -3328 |
| No stats, actual 64/side | NL -> NL | 4368 | 4368 | 0 |

Six improve, two unchanged, three regress. Every case returns identical ordered
pairs. The skewed matching-statistics case has 63 empty strings and one 10,000-byte
string per side. `min(mean bytes)` overestimates `mean(min(bytes))`, causing an
unprofitable hash choice. Stale estimates can also make a tiny join worse, as the
28 -> 48 case shows. No universal improvement guarantee is claimed.

## Verification and independent review

- Evaluator suite: **46 tests passed** in 9.300 seconds.
- Independent adversarial suite: **31 tests passed** in 5.200 seconds.
- Actual public CLI: independent identity and current optimizer each accept
  26 cases/70 conforming dataset executions. All five baseline mutants reject
  with retained witnesses; join-specific dropped-NULLEQ and swapped-column mutants
  reject in the independent specialist checks.
- Both specialists independently test exact position sequences, duplicates,
  NULL/NULLEQ, empty inputs, mixed INT/NUM precision, wide derived INTs, semantic
  errors, aliased destinations/inputs and register reassignment.
- Reviewer confirmed a literal-corruption bug caused by Python's broad line
  splitting. Coordinator reproduced failures before fixing it. LF-only parsing
  now passes all nine non-LF separator variants; regressions remain in tests.
- A preexisting evaluator false rejection of large stderr diagnostics was
  separately reproduced and fixed. Capture is bounded; excess diagnostics drain
  under the same deadline. Stdout floods remain fatal. Separate commit 11df850.
- Neither specialist imports optimizer code; VM execution and an independent
  Cartesian-pair oracle provide expected behavior. Review reports record test
  corrections separately from confirmed optimizer failures.

Raw final outputs are `tests-evaluator.txt` and `tests-adversarial.txt`. Detailed
specialist reports are `tests/evaluator/JOIN_REPORT.md` and
`tests/adversarial/JOIN_REVIEW.md` from the repository root.

## Runtime

Example optimizer calls: 79.6-80.5 ms each, including Python startup. Full public
evaluation of current optimizer: 4.304 s external wall, 4.195 s reported internal
wall; optimizer subprocesses total 2.075 s and paired VM execution 1.217 s.
Schema validation and startup explain additional wall time. Independent identity
took 2.660 s external wall in the same CLI demonstration. Single-run timings are
noisy; the small cycle saving does not establish an end-to-end wall-time gain.

An optimizer-only scale probe with 20,000 instructions, 19,997 joins and 20,000 schema
columns finished in 0.243 s. The fixture uses synthetic estimates; it is not a
worst-case runtime proof or VM-equivalence benchmark. Per-case timings, source
audit and algorithm cycles are retained in `examples.json`, `workloads.json`,
`cli-checks.json`, and `scale.json`.

## Reproduction

Run from the repository root, with the locally supplied interpreter in `bin/`:

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/evaluator -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -v
python3 tools/verify_baseline.py --output records/join-selection/cli-checks.json
python3 tools/benchmark.py ./optimize --output records/join-selection/examples.json
python3 tools/benchmark_joins.py ./optimize --output records/join-selection/workloads.json
python3 tools/probe_join_scale.py --output records/join-selection/scale.json
```

Artifacts are text-only; binaries and Python caches stay out of Git. Existing
baseline reports are preserved in `records/` as historical measurements.

## Publication and limits

The user confirmed pushing the baseline commits themselves. This environment
still cannot resolve GitHub, so new commits are local for the user to push. No
remote state or new push is claimed; no force push or history replacement.

Finite tests do not prove soundness. Resource-limit equivalence remains uncertain
because algorithm work accounting differs. Cost approximations are sensitive to
skew/stale statistics, aggregate cardinalities are unmodeled, and the evaluator
retains its documented finite-corpus/type-serialization limits. No other optimizer
rewrite has been added. AI model/reasoning settings and usage availability are
unchanged from `records/SESSION.md`; no token/spend numbers are invented.
