# AI use and recorded usage

The following model, reasoning and account details were supplied by the user.
They replace the earlier pending fields and generic runtime identification.

| Work | Tool / model | Reasoning |
|---|---|---|
| Development | Codex CLI, GPT-6.1 Sol | High |
| Independent review | Codex CLI, GPT-6 Astra | High |
| Separate brainstorming thread | GPT-6.1 Sol | High |

Usage was through **ChatGPT Plus**. The user reports consuming approximately
**four full five-hour usage allowances** across the assignment. This is a reported
usage-limit measure, not a token count or a measurement of elapsed development
time. Exact token counts were not recorded, so no reliable token total or
project-specific dollar cost is available. No conversion or cost estimate is inferred.

One coordinator implemented the optimizer, integrated the work, measured results
and coordinated Git. Two specialists worked independently on evaluator code/tests
and adversarial semantics/rewrite review. The user reviewed scope and tradeoffs
and approved implementation milestones. No nested delegation was used.

The user also used a **separate brainstorming thread to discuss next steps and
help draft subsequent prompts**. That conversation is **not included in the
submitted logs**. Its model and reasoning setting were clarified as GPT-6.1 Sol
with High reasoning.

Available prompts and assignments are retained in [records/PROMPTS.md](records/PROMPTS.md);
commands, results, decisions, failures, fixes and available specialist reports are
retained under records/ and tests/. These are curated development records, not a
complete provider-exported conversation/tool trace. The omitted brainstorming
conversation is a known gap in submitted log coverage. Temporary specialist
usage-limit errors occurred; later follow-ups completed the final independent checks.

With a few days and unlimited compute/tokens, priorities would be independent
schema/program generation, evaluator mutation testing, automatic shrinking of
failures, exhaustive small-input checks and explicit resource/lifetime analysis.
Broader fixed holdouts should precede cost-model complexity or additional rewrites.
More generated tests would provide evidence, not a proof of soundness.
