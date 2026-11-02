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
