# Development record

## Scope and authorization

- 2026-11-02: user requested a coordinator/optimizer implementer and exactly two
  specialists: an independent evaluator engineer and an adversarial reviewer.
- First turn was inspection/planning only. No repository source was modified.
- User approved the first baseline milestone only: capture the starter, establish
  Git, implement and challenge the evaluator, demonstrate identity acceptance and
  defective optimizer rejection. Stop and recommend the first optimization before
  adding rewrites.
- Routine commits and pushes to
  `https://github.com/armaankols/minivm-optimizer.git` are authorized. No force push
  or history replacement. Binaries, including all supplied `bin/`, stay local.

## Repository setup

- Workspace and supplied `aim-takehome/` initially had no Git repository. No
  applicable `AGENTS.md` was found in the inspected paths.
- `git ls-remote https://github.com/armaankols/minivm-optimizer.git` failed:
  `Could not resolve host: github.com` on both planning and implementation turns.
- `gh auth status` reports the configured account `armaankols` token invalid.
  Remote existence/history and push access are therefore **unverified**; a local
  origin URL is not evidence of connectivity.
- Initialized a local repository in the supplied bundle on `codex/baseline` and
  configured origin to the exact requested URL. Local commit author is
  `Codex <codex@localhost>`; global Git configuration was not changed.
- Commit `b8e7f8a` captures all 34 supplied text files, `STARTER.sha256`, and binary
  exclusion rules. The original `optimize` and `evaluate` scripts are in that
  commit before implementation. Supplied binaries are preserved locally.
- Before any future push: recheck remote access, inspect remote refs/history,
  fetch existing history, and choose an integration branch without replacing it.
- Subsequent user update: the user successfully pushed the baseline commits
  themselves. This is user-confirmed publication, not an independently observed
  push from this environment. The user authorized continued local commits when
  this environment cannot push and will handle those pushes themselves.
- At join-milestone start, `git ls-remote origin` still failed with GitHub DNS
  resolution error. Local history remained at `9a06eab` on `codex/baseline` with
  no unrelated or uncommitted changes. Do not claim the baseline is unpublished.

## Planning evidence and decisions

- Read assignment PDF, all docs, both scripts, all eight example programs,
  schema/data and expected JSON. No interpreter source was supplied.
- PDF tools were absent from system Python and `pdftotext` was unavailable.
  A temporary Objective-C PDFKit reader extracted the single-page assignment;
  another temporary PDFKit program rendered it for visual inspection. A Swift
  attempt failed due to installed SDK/module conflicts. No generated binaries or
  PDF/image artifacts enter the repository.
- Direct native VM invocations initially exited 137. The supplied wrapper works;
  it contains the bundle's macOS quarantine handling. Use `bin/minivm` in checks.
- All eight original examples exactly match supplied expected JSON including
  cycles: 13766, 3617, 8562, 18442, 5518, 6338, 2596, 1524.
- Stats are estimates only; semantic preconditions must use declarations.
- Plan: narrow join algorithm choice, proven-total dead computations, guaranteed
  sorted-prefix elimination, identity gathers, and version-aware exact CSE.
  **No rewrite has been authorized for this milestone.**
- Reviewer produced counterexamples for unrestricted DCE, unrestricted TOPK
  fusion, stale CSE aliases, sorted suffixes, and nullable check bounds.
- Coordinator independently executed the DCE and TOPK fixtures: originals exit 1
  for division by zero and a SORT type error; unsafe alternatives exit 0.
- Internal SSA/reaching-definition analysis must not blindly increase physical
  register lifetimes. Error/resource-limit equivalence needs separate treatment.

## Assignment policies adopted for the baseline

- CLI remains `./optimize program.mini schema.json` and `./evaluate OPTIMIZER`.
- Numeric tolerance: symmetric relative error using max absolute magnitude, with
  no absolute tolerance. This is an interpretation; denominator is unspecified.
- Fixture metadata defines final ordering and output types. NUM, wide INT, STR,
  and DATE share JSON string encodings; spelling alone is insufficient.
- Compare entire rows and preserve multiplicity and associations. Approximate
  unordered row comparison requires matching, not per-column bags or greedy
  matching.
- Freeze each optimizer schema while varying conforming datasets, so estimates
  cannot silently become guarantees.
- Preserve semantic error behavior conservatively. Resource exhaustion remains
  an explicit ambiguity in the assignment and opcode documentation.

## Team and ownership

- Coordinator: optimizer (unchanged identity for this milestone), integration,
  root documentation, `tools/`, `records/`, shared interfaces, and all Git actions.
- Evaluator specialist: `evaluate`, `evaluator.py`, `tests/evaluator/` only.
- Adversarial reviewer: `tests/adversarial/` only; communicates findings to the
  evaluator specialist and coordinator instead of modifying their files.
- No shared implementation helpers and no optimizer imports in evaluator code.
  No nested delegation. Parallel edits remain separate; coordinator stages
  completed paths explicitly.

## AI usage and provenance

- Runtime identifies this agent as Codex based on GPT-6. Specialist sessions
  inherit the parent configuration; no model override was requested or used.
- User supplied no specific model variant or reasoning setting. Exact backend
  model identifier, reasoning setting, token usage, and spend are not available
  in exposed usage metadata; they are unknown, not estimated numbers.
- `PROMPTS.md` retains the user requests and agent assignments. Available agent
  reports and concise execution results are retained with this milestone; this
  record is a curated transcript, not a claim of complete internal telemetry.

## Cost-model comparison and refinement

- User requested comparison against always-HJOIN and always-NLJOIN on the same
  workloads, independent investigation of matching-stat string skew, and a
  defensible cost-only improvement before another rewrite. Two existing
  specialists retained their ownership; no nested delegation or model override.
- Before any optimizer edit, coordinator saved `join-costs/before.json` for the
  unchanged 8 examples + 11 targeted workloads. Reference optimizer text is
  recovered from Git commit 3155414 and run through its command interface. Forced
  policies also run as executables. Every candidate is audited for opcode-only
  changes and executed against the same schema/data. Evaluator independently
  copied the corpus and confirmed all raw cycles by documented formulas.
- Reviewer independently derived seed NL 22180 / H 28852. Only one long/long pair
  contributes 10000 byte cycles; min(mean) incorrectly assigns 640000 byte cycles
  across 4096 pairs. The means themselves match the data; their use loses shape.
- Based on that independent finding, added direct-LOAD string length profiles:
  NULL zero-byte mass, common UTF-8 lengths/counts and a residual-mean bucket.
  Constant FILL has exact metadata; GATHER/SLICE/element-wise operations discard
  profiles. Retained scalar means are only heuristic fallbacks. No operand,
  flag, instruction ordering or non-join source byte changes.
- Decimal rounding intervals recover unique integer byte totals where possible;
  otherwise an uncertainty margin keeps the original opcode near a rounded tie.
  Counts/common values/distinct metadata and inferred residual totals are checked;
  inconsistent profiles fall back. Rounding margins do not bound unknown tail
  shape or statistical drift.
- Reviewer supported the general residual-mean estimate but retained truncated
  tail and stale-profile counterexamples. Initial cost-choice tests were red
  against the old model, not semantic failures; after refinement they passed
  without expectation changes. No new semantic failure was confirmed.
- Fixed 19 comparison: previous 112833, refined 106161, always H 137963, always NL 449799.
  Exactly one refined case improves by 6672, eighteen unchanged, no new regression
  on this fixed set. Examples remain 60167 for selected, 60567 always H, 72953 always NL.
- Separate holdouts are not substituted into those totals. They retain a matching
  heterogeneous-tail regret 21358 vs 18655 and a NEW stale-profile regression from
  old H 9232 to refined NL 16528. Derived profiles intentionally fall back and may
  keep poor choices. These are performance limitations, with identical results.
- Final coordinator suites: 59 evaluator tests passed 19.026 s; 41 adversarial tests
  passed 8.507 s. All preceding semantic/lexical/process tests remain included.
  Public evaluator still passes 26 cases / 70 datasets, wall 4.331 s, optimizer sum 2.156 s,
  paired VM 1.252 s. Optimizer-only 20k-instruction/ 20k-column probe finishes 0.255 s.
- Full before/after policy tables, raw measurements, separate holdouts and command
  output are retained in `join-costs/` and specialist COST reports. Historical
  baseline and first join-milestone records remain unchanged. No new token/spend
  or backend model telemetry is available; none is invented.

## Remaining risks and deferred work

- GitHub connectivity/authentication and remote history verification.
- Finite tests cannot prove optimizer soundness or detect every possible defect.
- Ordering intent, numeric denominator, and behavior on failing originals are
  underspecified. Test metadata and documented policies bound these ambiguities.
- Broad rewrites and a general constraint solver are deferred.
- Additional rewrites beyond this milestone's conservative DCE await user review.

## Balanced freeze and conservative DCE

- User requested the combined join tradeoff and a complexity recommendation,
  then authorized the next conservative rewrite with independent review and
  separately measured contribution. Later status questions did not cancel work.
- Combined arithmetic: fixed 19 plus stale-profile holdout is 122065 simple versus
  122689 refined (+624); all 29 cases are 341953 versus 328560 (-13393). Both are
  reported. These unweighted related diagnostic cases do not establish workload
  probabilities. Freeze 315 simple on scope/complexity grounds, not a performance
  dominance claim; archive exact 48 source and all profile tests/measurements.
- Full CLI now joins then DCE; --joins-only isolates the frozen cost stage.
  DCE uses guaranteed types, exact known opcode roles and backward liveness,
  retaining every potentially failing instruction and its inputs. Only a narrow
  whitelist is eligible; no statistics justify semantic removal. Unknown syntax
  disables the pass. Removed lines preserve comments and physical line endings.
- Coordinator found and reproduced a successful-source resource regression:
  removing dead LOAD overwrites after eight 2000x2000 HJOINs retained old large
  columns; original exit 0 versus candidate exit 1 at line 23 memory > 64000000 values.
  Complete program/candidate and results saved before fix. First-textual-definition
  guard now keeps all overwrites; after-fix result matches original including
  cycles 64226104. Both specialists reviewed and added lightweight guards; neither
  duplicated the heavy probe. This is stronger than merely documenting ambiguity
  for originally failing runs.
- Final coordinator suites: 75 evaluator tests pass 25.125 s and 57 adversarial tests
  pass 17.141 s. All existing tests, archived profile coverage and join holdouts
  remain. Public identity/current pass 26 cases / 70datasets; five mutants reject.
- Separate DCE measurement: examples 60167->59891, saving 276 (q1:34,q2:90,q7:152;
  five unchanged,no regressions). Eleven targeted join cases and ten holdouts
  unchanged. Three separate positive fixtures save 88,24,56 cycles. All32 benchmark
  outputs agree exactly; join choices are held fixed across the DCE comparison.
- Unoptimized example total 60363->59891 combines 196 join plus 276 DCE savings.
  This does not claim to overcome the archived profile gain across all 29 cases.
- Public current wall 4.325 s; per-example optimizer 80-82ms; optimizer-only 20k scale
  probe 0.336 s. Startup included, timings noisy. Reports/raw logs and reproduction
  tools are retained in records/dce and both specialist DCE reports.
- No additional join tuning or rewrite was added. Model settings and unavailable
  usage telemetry are unchanged. Binary exclusion and local-commit/push policy
  remain as authorized; remote state is not inferred from user-reported pushes.

## Join milestone authorization

- User approved only join algorithm selection between NLJOIN and HJOIN,
  preserving every operand and flag. Independently review equivalence and edge
  cases, run existing checks, measure cycles including small joins where a
  switch can be worse, commit the verified change, then stop before any other
  rewrite. Coordinator owns optimizer and integration; existing specialist
  ownership is unchanged. No nested delegation.
- Cost estimates are not semantic proofs. Single-pass row, type, distinct-count
  and byte estimates may guide selection; unsupported estimates leave the join
  unchanged. Output emission must replace only the opcode token, preserving all
  remaining source bytes, including comments, CRLF and trailing newline state.

## Join milestone implementation and verification

- Added `optimizer.py` and changed the optimize wrapper. Only recognized NLJOIN
  or HJOIN opcode spans can change. All operands, optional NULLEQ, register names,
  comments, literals, other instructions, CRLF and final-newline state survive.
- Single-pass estimates: direct LOAD rows/type/NDV/mean bytes, shape-preserving
  operations, 50% IDX selectivity, uniform-NDV join-size estimates where possible.
  Group/aggregate cardinalities and unknown estimates stay unmodeled. These facts
  guide costs only; they never justify dropping pairs or changing operands.
- Independent reviewer found a confirmed correctness failure before the fix:
  Python splitlines exposed fake join text inside valid string literals with
  Unicode/control separators. Coordinator reproduced four failing subtests in
  an actual 12-test run before editing the lexer. Reviewer confirmed five more
  separators. Fixed by splitting only on LF. All nine retained variants pass.
- Reviewer also flagged a quadratic schema-column stats lookup as a suspected
  scaling risk, without reproducing a timeout. Replaced it with one case-folded
  map per table. No timeout failure or isolated speedup is claimed for that change.
- Evaluator specialist independently reproduced an existing harness false
  rejection: correct identity with 300000 stderr bytes became Defect. Coordinator
  authorized a narrow fix: truncate captured stderr while draining excess under
  the original deadline; stdout over 4 MiB remains fatal. Both specialists tested
  it. Coordinator did not independently execute the pre-fix stderr reproduction.
  Separate commit `11df850` records the reviewed harness fix and regressions.
- Coordinator reran all existing and new checks: evaluator 46 tests passed in
  9.300 seconds; adversarial 31 tests passed in 5.200 seconds. Raw output is in
  `join-selection/tests-evaluator.txt` and `tests-adversarial.txt`.
- Public CLI demonstration now uses an explicit independent identity fixture
  and separately tests the current optimizer. Both pass the unchanged default
  26-case/70-dataset corpus; all five retained defective optimizers exit 1 with
  witnesses. Join-specific drop-NULLEQ and swapped-pair mutants are also rejected
  in specialist tests and explicit specialist CLI probes.
- Fixed eight-example comparison: 60,363 -> 60,167 cycles, saving 196 (0.3247%).
  q0001 line31 changes HJOIN to NLJOIN; every other supplied example is byte
  identical. No example regressions. Exact rows/representations/order and source
  differences (opcode only) are audited by the benchmark.
- Eleven targeted workloads: 6 improve, 2 unchanged, 3 regress. Preserve rather
  than hide stale-stat regressions 28->48 and 1040->4368, and matching-statistics
  skewed-string regression 22180->28852. All ordered pairs remain identical.
- Recorded example optimizer wall time: about 79.6-80.5 ms per invocation.
  Public current-optimizer evaluation: 4.304 s external wall / 4.195 s internal,
  optimizer subprocess sum 2.075 s, VM execution sum 1.217 s. Identity in this run
  takes 2.660 s external wall. Startup is included; timings are noisy. No claim of
  end-to-end wall-time improvement is made from the small cycle reduction.
- Optimizer-only scale probe: 20,000 instructions and 20,000 schema columns
  processed in 0.243 seconds; all 19,997 choices match expectation. This uses
  synthetic estimates and is not a worst-case proof or a VM-equivalence test.
- Commands, exact reports and reproducible scripts are retained under
  `join-selection/`, `tools/`, and both specialist JOIN reports. Original
  baseline snapshots remain unchanged. No second optimizer rewrite was added.
- Final remote check still reports `Could not resolve host: github.com`.
  Baseline publication remains user-confirmed; new agent commits stay local for
  the user's pushes. No force push or remote-history replacement was attempted.

## Baseline implementation progress

- `python3 tools/benchmark.py ./optimize --output records/benchmark-baseline.json`
  passed all eight exact expected checks and byte-identity checks. Total cycles:
  60,363 before and after; all eight unchanged; no improvements or regressions.
  One measured benchmark invocation took 0.410 seconds including subprocesses.
- First coordinator `./evaluate ./optimize` run passed 26 cases / 70 dataset
  executions in 2.166 seconds. This precedes final independent-review completion.
- Reviewer found ordered annotations on two no-SORT programs were too strict;
  evaluator owner changed them to unordered. This is a comparator-contract fix,
  not an optimizer rewrite.
- Coordinator reproduced a real robustness issue before its fix:
  `cell_equal('1.0', '1e1000000', 'NUM')` raised `decimal.Overflow`.
  An external optimizer emitting `LOAD x,t.x; LOAD s,t.s;
  FILL bad,'1e1000000',x; OUT bad,s` also raised the raw exception during
  evaluation and retained no witness. Sent exact witness to evaluator owner and
  reviewer for regression coverage and correction before baseline acceptance.
- Coordinator reran the reviewer's 11-test adversarial suite successfully before
  the overflow fix, including 100 exhaustive small matching cross-checks and 17
  semantic VM executions. Passing checks did not exclude the newly found issue.
- Coordinator then reproduced a false rejection caused by enforcing INT
  serialization on candidate numeric values. Original `LOAD x,t.x; OUT x` on
  stored INT values `[1,2,NULL]` and candidate `LOAD x,t.x; ADD y,x,0.1;
  SUB y,y,0.1; OUT y` produce equal numeric values, but the candidate prints
  `["1.0","2.0",null]` and was rejected. For stored signed-32-bit INTs this
  transformation has exact decimal arithmetic and cannot overflow. Assignment
  numeric tolerance applies to both numeric kinds. Sent reproduction for a fix
  and independent regression review; no optimizer rewrite was added.
- Both numeric findings are fixed and independently reviewed. Numeric string
  spellings are bounded canonical finite decimals, with Decimal exceptions
  guarded. Expected INT and NUM slots share numeric comparison; BOOL remains
  distinct and STR exact. Reproduction and acceptance regressions are retained.
- Final coordinator checks: evaluator suite 30 tests passed in 4.777 seconds;
  independent adversarial suite 17 tests passed in 1.928 seconds. Full command
  output is retained in `tests-evaluator.txt` and `tests-adversarial.txt`.
- `python3 tools/verify_baseline.py --output records/cli-baseline.json` accepted
  supplied identity (26 cases / 70 dataset executions) and rejected all five
  deliberate defective optimizers through `./evaluate OPTIMIZER`. Final measured
  CLI identity wall time was 2.249 seconds; evaluator internal wall time 2.142
  seconds, optimizer subprocess sum 0.090 seconds, paired VM sum 1.193 seconds.
  Schema validation/startup explain the remainder; these are single-run timings.
- Retained all five complete text witnesses under `records/witnesses/` and
  re-executed both original and candidate programs for each. All ten results
  exactly reproduced the saved JSON, including cycles.
- Commit `0a91af9` records the reviewed evaluator and specialist test/report files.
  Coordinator staged only finalized owned paths; no unfinished agent changes
  were included. `optimize` remains byte-identical to the starter commit.
- Final `git ls-remote origin` still failed GitHub DNS resolution; `gh auth status`
  still reported the configured token invalid. No push was attempted because
  required remote history verification could not succeed. No remote history was
  fetched or replaced. These are local commits, not published commits.
