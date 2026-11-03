# AI use and outstanding usage metadata

AI was used throughout, as required by the assignment. One coordinator implemented
the optimizer, integrated the work, measured results and coordinated Git. Two
specialists worked independently: evaluator design/code/tests and adversarial
semantics/rewrite review. No nested delegation or model overrides were requested.
The user reviewed scope and tradeoffs and approved each implementation milestone.

The runtime identified the agents as Codex based on the GPT-6 family. This is not
an authoritative exact backend model identifier. Specialist sessions inherited
the parent configuration; the user supplied no exact model or reasoning setting
in the recorded task prompts.

| Required detail | Current status |
|---|---|
| Exact model ID(s) shown by the product | **Pending user information** |
| Reasoning setting(s) | **Pending user information** |
| Approximate total tokens or spend | **Pending user/account telemetry** |

On request, the user said they would provide this information later. These fields
are intentionally unfilled; no token, cost, human-time or model-setting estimate
is invented. If account telemetry is unavailable, the final write-up should say
so explicitly. The assignment requests rough tokens or spend, so this remains a
submission-completeness item for the user rather than a claimed completed field.

Available prompts/assignments are retained in `records/PROMPTS.md`; important
commands, results, decisions, failures, fixes and specialist reports are retained
under records/ and tests/. This is a curated development record, not a complete
provider-exported chat/tool trace. A full export should be supplied if available
and required by the submission's request for all prompts/logs. Temporary specialist
usage-limit errors occurred; later follow-ups completed the final independent checks.

With a few days and unlimited compute/tokens, I would prioritize independent
schema/program fuzzing, mutation testing of the evaluator, automatic shrinking
of witnesses, exhaustive small-state checks and explicit resource/lifetime
analysis. A broader fixed holdout collection should precede cost-model complexity.
Only then would I revisit identity gathers or version-aware CSE with enforceable
preconditions. More generated tests would provide evidence, not a proof of soundness.
