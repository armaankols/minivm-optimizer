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

## Remaining risks and deferred work

- GitHub connectivity/authentication and remote history verification.
- Finite tests cannot prove optimizer soundness or detect every possible defect.
- Ordering intent, numeric denominator, and behavior on failing originals are
  underspecified. Test metadata and documented policies bound these ambiguities.
- Broad rewrites and a general constraint solver are deferred.
- Add no optimizer rewrites until the user reviews baseline results.

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
