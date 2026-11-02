These executable witnesses derive expectations from the supplied MiniVM semantics,
not optimizer internals. The paired variants intentionally demonstrate unsafe
candidate rewrites; their differences are expected, rather than optimizer defects.
Erroring originals are semantic boundary probes, not positive evaluator cases.

Run `python3 -m unittest discover -s tests/adversarial -v` from the bundle root.
Only the interpreter supplied locally is used; it is not part of the submission.

Relevant contracts: `docs/instructions/README.md` (NULL-first row-wise type checking),
`docs/values.md` (register reassignment, numeric ranges), `docs/running.md`
(constraints versus statistics), `docs/instructions/sorting.md` (stable sort,
comparison algorithms), and `docs/instructions/joins.md` (pair multiplicity,
ordering, NULL matching).
