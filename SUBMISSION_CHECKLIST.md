# Submission checklist

New optimizations are frozen at `49c7048`; current HEAD includes the
[post-review correctness fixes](records/post-review/RESULTS.md).
Start with [REVIEW_HANDOFF.md](REVIEW_HANDOFF.md) and [WRITEUP.md](WRITEUP.md).

| Item | Status and evidence |
|---|---|
| Specification and interfaces | [Requirements transcript](docs/assignment.md), original MiniVM docs and [contract](records/CONTRACT.md). Original PDF remains outside Git. |
| Setup | [SETUP.md](SETUP.md): Python standard library, POSIX and the original local interpreter bundle. No binaries submitted. |
| Fresh-checkout verification | Full-history local clone at `49c7048`: 75 evaluator + 75 adversarial tests passed; public evaluator passed 26 cases / 70 executions. Clean Git status before and after. [Receipt](records/submission-audit/clean-checkout.json). Same macOS host; network installation and other platforms unverified. |
| Post-review fixes | Separate pristine oracle and final UTF-8 file-size guard, with generated regressions and retained before/after evidence. See [results](records/post-review/RESULTS.md). |
| Identity and incorrect optimizers | Baseline receipts and witnesses retained; replay with `tools/verify_baseline.py`. Identity accepted, five deliberate defective optimizers rejected. |
| Reproducible results | Fixed workloads, holdouts, seeds, raw JSON, failure fixtures and commands retained. [Current results](records/sorted-order/RESULTS.md), [join tradeoffs](records/join-costs/RESULTS.md). Reproduction commands corrected from `python 3` to `python3`; use temporary result paths in SETUP. |
| Narrative and limitations | [WRITEUP.md](WRITEUP.md), handoff and per-rule proofs cover implementation, evaluator, measurements, join regressions, error preservation and memory lifetime. |
| AI use | [AI_USAGE.md](AI_USAGE.md) records user-reported Codex CLI models: GPT-6.1 Sol / High for development and GPT-6 Astra / High for independent review; brainstorming also used GPT-6.1 Sol / High. ChatGPT Plus usage was approximately four full five-hour allowances. Exact tokens and reliable project-specific cost are unavailable. |
| Prompts and logs | Curated prompts, assignments, decisions, commands, results and available specialist reports retained. A separate brainstorming thread discussed next steps and helped draft prompts; it is not included in submitted logs. A complete provider conversation/tool export is unavailable in the repository. This is a disclosed coverage gap. |
| Git history and binaries | At frozen commit: 10 commits, 34 starter hashes verified, 195 historical blobs checked as UTF-8 without NUL, no binary blobs or tracked bin files. [Audit](records/submission-audit/git-audit.json). Documentation preparation was text only; later review fixes add source and generated-boundary regression tests. |
| Publication | Requested origin configured. User confirmed earlier pushes. Latest remote state cannot be checked here because GitHub DNS fails. User handles pushes and should confirm the final branch/commit is accessible. No history rewriting. |

## Information still needed from the user

- Any available conversation export to supplement the curated logs, especially
  the separate brainstorming conversation disclosed as absent from the submission.
  Model/reasoning details and a usage-allowance estimate have now been supplied;
  exact token totals and a reliable project-specific dollar cost are unavailable.
- Confirmation that the final commits have been pushed and the submission reviewer
  can access the intended branch. Any portal-specific packaging instructions have
  not been supplied.

These items must not be filled with guesses. Finite test coverage, ambiguous error
and resource equivalence, VM output typing and cross-platform validation remain
technical limitations, not fields the user is expected to resolve.
