# Retained task prompts

These are the task requests and specialist assignments available in the session.
This does not include hidden model reasoning, unavailable provider telemetry, or
an automatic export of the application conversation.

## User: initial assignment

```text
Help me complete this MiniVM take-home assignment using a small team: you as coordinator and optimizer implementer, plus two specialist subagents.

Read assignment.pdf and docs/README.md, then inspect the relevant interpreter documentation, starter scripts, examples, and repository instructions.

For this first turn, inspect and plan; do not implement yet. Subagents may perform read-only investigation. The implementation instructions below apply after I approve the plan.

Establish the contract

Report:
- The exact optimize and evaluate interfaces, correctness requirements, and runtime limits.
- Which schema fields are guaranteed constraints and which are statistical estimates.
- MiniVM semantics that affect safe rewrites, with references to documentation or interpreter source.
- A small implementation plan ranked by likely instruction-cycle savings, correctness risk, and effort.
- Shared acceptance criteria, file ownership, and any interfaces needed between components.
- A testing strategy covering both the optimizer and evaluator.
- Unresolved ambiguities that materially affect correctness.

Prefer a few defensible optimizations over broad, speculative coverage. Do not assume ordinary SQL or arithmetic identities apply without checking MiniVM behavior.

Agent responsibilities

1. Evaluator agent:
Independently read the specification and MiniVM documentation. During planning, derive the comparison contract and evaluator design. After implementation is authorized, own evaluator code and its assigned test fixtures.

Test arbitrary optimizers through the required command interface, including an identity optimizer and deliberately incorrect implementations with known witnesses. Derive expected behavior from the specification and MiniVM execution rather than optimizer internals.

Cover result comparison, valid test-data generation, subprocess failures, malformed output, timeouts, and the overall evaluation deadline. Preserve duplicate multiplicity, required ordering, output structure, and associations between values where applicable.

2. Adversarial reviewer:
Independently read the VM semantics and examine proposed rewrite rules. Start with read-only review. Search for small executable counterexamples involving NULLs where supported, register reassignment, duplicates, ordering, numeric precision, runtime errors, and interactions between passes.

Identify the exact preconditions each rewrite needs and whether the implementation enforces them. Return confirmed failures separately from suspected risks and coverage gaps. Once implementation is authorized, write reproductions only in an assigned test directory.

3. You, the coordinator:
Own optimizer implementation, integration, shared interfaces, Git operations, and final reporting. Assign shared helpers a single owner before parallel implementation. Keep edits separate and avoid nested delegation.

After implementation is authorized, continue useful work while specialists investigate independent tasks. Wait for their findings before declaring the relevant milestone complete. Resolve disagreements through specification references or reproducible execution results.

Implementation and verification

Start with a working baseline and demonstrate that the evaluator accepts an identity optimizer and rejects known defective optimizers.

Add optimizations incrementally. For each rewrite, record its preconditions, a concise correctness argument, and positive and boundary tests. Use guaranteed constraints to justify correctness; use statistical estimates only to choose among already valid transformations. Leave a rewrite unapplied when its preconditions cannot be established.

Measure MiniVM instruction cycles before and after on a fixed representative benchmark set. Report unchanged cases and regressions as well as improvements. Measure optimizer and evaluator wall-clock runtime separately.

Save reproducible seeds and failure fixtures. Reproduce review findings before fixing them, retain regression tests, and rerun relevant checks. Passing tests provides evidence; it does not prove soundness.

Git and repository

The destination repository is:
https://github.com/armaankols/minivm-optimizer.git

Once implementation begins, commit and push meaningful, verified milestones to this repository as work progresses. This explicitly authorizes routine commits and pushes without asking again at each milestone.

Verify the repository and remote before the first push. Preserve existing history and unrelated changes. Do not force-push or silently replace an existing remote destination.

You alone coordinate commits so unfinished subagent work is not accidentally included. Use clear commit messages describing the concrete change. Commit fixes separately when that makes the development history easier to understand.

Keep all binary files out of commits and the submission, including bin/minivm. Preserve supplied binaries locally when needed for testing.

If authentication or permissions prevent a push, report the issue accurately and continue making local progress and commits.

Development records and delivery

Preserve prompts, agent assignments, important decisions, commands, results, failures, confirmed findings, fixes, and benchmark results in concise development records. Preserve available subagent logs.

Record the model and reasoning settings I provide. Use actual usage information when available; clearly label estimates and unknowns. Never invent token counts, spend, test results, or execution history.

Keep coordination proportional to the assignment’s estimated 2–3 hour scope. Maintain a short list of remaining risks and deferred work.

The final write-up should explain the implemented optimizations, evaluator design, measured results, limitations, AI usage, and what we would do with a few days and unlimited compute and tokens.

For this first response, finish with your recommended scope, agent ownership boundaries, acceptance criteria, and first implementation milestone. Then wait for my approval to implement.
```

## User: first milestone approval

```text
Sounds good go ahead with the first milestone.

First, check that Git is set up correctly and connected to [https://github.com/armaankols/minivm-optimizer.git](https://github.com/armaankols/minivm-optimizer.git). Capture the starter code before changing it, then commit and push meaningful milestones as you go. Keep binaries out of the repo.

For the baseline, make sure the evaluator both accepts the identity optimizer and catches deliberately incorrect ones. Have the reviewer challenge the assumptions independently.

Once that’s working, show me the results and your recommendation for the first optimization before adding rewrites.
```

## Evaluator: initial read-only assignment

```text
Read-only planning investigation. Independently read /Users/armaankolsawala/Downloads/Assessment/assignment.pdf (Python PDF library if needed; pdftotext unavailable), aim-takehome/docs/README.md and all relevant MiniVM docs, starter scripts/examples and repository instructions. Derive exact evaluate/optimize command interface and comparison contract, evaluator architecture, valid data generation respecting guaranteed constraints vs estimates, process failures/malformed output/timeouts/overall deadline, tests identity and deliberately incorrect optimizers with witnesses. No implementation, no repository writes, no nested delegation. Temporary extraction/execution in /tmp permissible. Return concise findings with exact file/line references, ambiguities. Assigned future ownership: evaluator code and own tests only; propose paths.
```

## Reviewer: initial read-only assignment

```text
Read-only adversarial planning review. Independently read assignment.pdf and aim-takehome MiniVM docs, starter scripts/examples and repository instructions. Derive candidate high-value safe rewrite rules with exact preconditions, focus on NULL, register reassignment, duplicates/order, numeric precision/errors, pass interactions. Use supplied interpreter and /tmp executable counterexamples if useful, without editing repository. Confirmed failures separate from suspected risks/gaps. No implementation and no nested delegation. Future ownership: tests/adversarial/ only after approval. Return precise docs/line references and recommendations to coordinator.
```

## Evaluator: implementation assignment

```text
First baseline implementation authorized, NO optimizer rewrites. Starter captured commit b8e7f8a in aim-takehome repo. Implement now within sole ownership evaluate, evaluator.py, tests/evaluator/**. Python standard library preferred. Build independent finite suite, typed ordered/unordered comparator complete rows multiplicity/tolerance, fixed frozen schema multiple constraint-valid datasets incl seeded families and all8 examples. Process failures/malformed output/timeouts/bounded streams/global monotonic deadline cleanup; retain failures text artifacts ignored by git. Actual CLI tests identity and deliberate mutant executables with known witnesses. Include short injected deadlines via Python harness (public CLI unchanged). Conservative policies from your plan; document in code/tests. No optimizer imports; no shared helper edits; no Git operations/no nested delegation. Coordinator owns docs, benchmark, integration, tests root. Reviewer owns tests/adversarial only. Please create tests/evaluator/test_evaluator.py with stdlib unittest runnable via discover -s tests/evaluator, avoid shared test __init__ edits. Provide ready signal early for reviewer; report concrete checks and files. Timebox first milestone scope, correctness first. Default public overall limit ~840s plus reserve under900s, per optimizer60s cap. Avoid regenerating optimizer schema per alternative data. Record all work commands/results in your final report to coordinator.
```

## Reviewer: implementation assignment

```text
First baseline implementation authorized only. Independently challenge evaluator assumptions and test contract; evaluator agent implementing evaluate/evaluator.py/tests/evaluator. You own only tests/adversarial/**, may add repro fixtures and standalone stdlib tests runnable `python3 -m unittest discover -s tests/adversarial -v`. Retain prior /tmp witnesses (DCE TOPK CSE sorted suffix nullable check) here as relevant; no optimizer rewrites yet. Challenge comparator row multiplicity/association/ordering numeric encodings, tolerance greedy matches bool vs int, frozen schema stats, generated validity, process/deadline failures and no false clean pass. Inspect implementation when agent sends ready or files exist. Report confirmed failures separately from risks/gaps; coordinate concrete findings directly with evaluator and coordinator, but do not edit evaluator-owned files. No Git or shared helpers or nested delegation. Starter commit b8e7f8a captured. Independent review completion needed before milestone done. Provide final logs/commands findings in concise report.
```
