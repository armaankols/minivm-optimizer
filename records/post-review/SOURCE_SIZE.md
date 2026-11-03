# Final source-size guard review fix

Finding: [supplied fresh review](supplied-REVIEW.md), P2 program file expansion.
Spec: `docs/running.md` permits files up to 4 MiB inclusive.

Before fixing, the coordinator reproduced the supplied successful original on all
three optimizer modes: 4,194,304 input bytes became 4,194,305 bytes; candidate VM
exited 1 with `larger than 4 MB`. Both join outputs were live, so DCE did not hide
this boundary. Reviewer independently reproduced the same failure.

Fix: encode the final candidate after every enabled pass. If its byte length is
above 4,194,304, output the original input bytes. For a valid original this fallback
preserves all behavior. UTF-8 bytes, rather than Python character counts, determine
the boundary. Later deletions may offset expansion, so checking only the join pass
would discard safe improvements unnecessarily. No new rewrite was added.

After fixing, the supplied witness on all three modes emits byte-identical
4,194,304-byte original source, succeeds, and returns rows [[0,0]], cycles 27.
Generated boundary tests also check candidate exactly at the limit, multibyte
comments, DCE offsetting growth and a normal small join still improving.

Coordinator command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/adversarial -p test_source_byte_limit.py -v
```

Five tests passed in 1.808s; independent reviewer run passed in 1.654s. These tests
invoke the public optimizer and supplied VM, without optimizer imports. Padding
is generated in temporary directories; no 4 MiB fixture or binary is committed.
Before/after raw receipts and the coordinator log are beside this document.
