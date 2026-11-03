# First milestone: verified identity baseline

No optimizer rewrites are included. `optimize` is byte-identical to the supplied
identity script captured before evaluator changes.

## Results

| Check | Observed result |
|---|---|
| Evaluator tests | 30 passed, 4.777 seconds |
| Independent adversarial tests | 17 passed, 1.928 seconds |
| Public CLI identity | exit 0; 26 program cases, 70 conforming dataset executions |
| Public CLI defective optimizers | all five exit 1 with retained witnesses |
| Supplied example cycle total | 60,363 before / 60,363 after |
| Improvements / unchanged / regressions | 0 / 8 / 0 |

Five command-interface mutants deliberately return empty results, drop duplicate
rows, swap output columns, break row associations, or replace NULL with zero.
Their sources, exact statuses, diagnostic text, and timing are retained in
`cli-baseline.json`; complete data/program/schema/result witnesses are under
`witnesses/`. Both programs in each witness were rerun and all ten saved results
reproduced exactly, including cycles.

Additional harness tests cover numeric tolerance, numeric-looking strings,
BOOL/INT distinction, output structure, malformed output, nonzero exits, missing
executables, stdout/stderr limits, process and child cleanup, VM failures, frozen
stats, declaration validity, and overall deadline exhaustion. The reviewer also
retained eight VM semantic boundary witnesses (17 VM executions) and checked
approximate row matching against a small exhaustive oracle on 100 seeded cases.

Independent review and integration corrected overly strict ordering annotations,
a raw Decimal overflow/no-witness failure, and a false rejection of numerically
equal INT/NUM output representations. Reproductions and chronology are retained
in both specialist reports. No unresolved evaluator failure is currently
confirmed. Passing these finite tests does not prove soundness.

## Timing

Final recorded identity CLI wall time: 2.249 seconds. Its evaluator summary reports
2.142 seconds internally, including 0.090 seconds across optimizer subprocesses
and 1.193 seconds across original/candidate VM execution pairs. VM time excludes
schema validation; total wall includes it. The default evaluator budget is 840
seconds, below the assignment's 900-second cap; optimizer calls are capped at 60
seconds. Tests inject short deadlines to exercise timeout handling.

The fixed eight-example benchmark took 0.410 seconds in its recorded run. Its
identity optimizer subprocesses took approximately 0.0033–0.0049 seconds when
warm; the first measured invocation took 0.180 seconds. Timing includes process
startup and is noisy. Full per-program data, including unchanged cases, is in
`benchmark-baseline.json`.

## Git and deliverables

Local repository: supplied `aim-takehome/` bundle, branch `codex/baseline`.
Origin is the exact requested URL:
`https://github.com/armaankols/minivm-optimizer.git`.

Starter commit `b8e7f8a` preserves all 34 original text files with checksums.
`be3395a` records the initial baseline measurements and contract; `0a91af9`
records evaluator and independent review code/tests. Local author metadata is
`Codex <codex@localhost>`; global Git configuration was preserved.

At baseline handoff, remote verification failed with `Could not resolve host:
github.com`; GitHub CLI also reported its configured token invalid. No agent push
occurred. The user subsequently confirmed that they successfully pushed these
commits themselves. That publication is user-reported; this environment still
cannot independently inspect remote history. The user will handle further
pushes if agent connectivity remains unavailable. No force push.

The whole supplied `bin/` directory, generated binary artifacts, and Python caches
are excluded. The PDF remains outside the repository. Submitted/tracked files
are checked as UTF-8 text without NUL bytes. The local interpreter is preserved
for testing and is not included in Git.

## Recommendation before adding any rewrite

Start with **join algorithm selection**, preserving both destination operands,
input versions, and NULLEQ exactly. The MiniVM documentation explicitly gives
NLJOIN and HJOIN the same pairs, multiplicity, order, and semantic errors. Use
stats only to choose the estimated cheaper equivalent operation; numeric join
work excluding common output cost is approximately L*R versus 6*(L+R). Include
string byte estimates and leave unknown estimates unchanged. Tiny joins may
favor NLJOIN, so do not blindly replace all NLJOIN instructions with HJOIN.

This is the smallest defensible next change. Test empty sides, duplicates,
NULL/NULLEQ, INT/NUM equality, incompatible types, aliased destinations, and
register reassignment, then report per-case cycles and wall time. Resource-limit
failure equivalence remains a documented caveat because work accounting differs.

Next candidates are proven-total dead computations, guaranteed sorted-prefix
elimination, identity gathers, and exact CSE with reaching definitions. Broad
TOPK, arithmetic, pushdown, and self-join rewrites remain deferred. No rewrite
will be added until the user reviews this baseline.

## Limits and AI usage

Ordering intent, the relative-error denominator, and equivalence for failing
originals are underspecified. Policies are explicit in `CONTRACT.md`. Mixed-type
output columns and arbitrary-schema generation are deferred; JSON type-encoding
overlap cannot universally distinguish numeric-looking STR from numeric output.
Process cleanup targets POSIX and is not a security sandbox.

One coordinator and exactly two specialists were used, with no nested delegation.
Available prompts, assignments, decisions, execution logs and reports are retained.
At this milestone, the runtime identified Codex based on GPT-6; exact model/reasoning
settings and usage were not yet supplied. The later user-reported models, settings,
usage allowances and log omissions are recorded in [AI_USAGE.md](../AI_USAGE.md).
Exact token totals and reliable project-specific cost remain unavailable.

With additional days and compute, prioritize generated schema/program families,
metamorphic tests and mutation testing, shrinking counterexamples, explicit type
and row-domain analysis, resource-bound stress cases, and broader benchmarks.
Only expand rewrite coverage after establishing enforceable preconditions.
