# Three-way catalog merge demo

Two translation branches (`ours.po`, `theirs.po`) both descend from
`base.po`. `run_merge.py` merges them with
`babel.messages.merge.merge_catalogs`, writes `merged.po`, and prints
which entries were merged automatically and which need a human decision:

    python misc/three-way-merge/run_merge.py

## What is in the demo

| Entry | ours changed | theirs changed | Result |
| --- | --- | --- | --- |
| `hello` | translation | location + translator comment | **auto-merged** (both kept) |
| `quit` (ctxt `menu`) | translation | translation | **conflict** (`translation`) |
| `apple`/`apples` | added a 3rd plural form | edited the 2 existing forms | **conflict** (`plural-length`) |
| `legacy` | deleted | translation edited | **conflict** (`delete-vs-modify`) |
| `old_feature` | resurrected from obsolete | left obsolete | **auto-merged** (resurrected) |
| `Last-Translator` header | Bob | unchanged | **auto-merged** (Bob) |
| `Language-Team` header | unchanged | German Team | **auto-merged** (German Team) |
| `PO-Revision-Date` header | 2025-03-01 | 2025-04-01 | **auto-merged** (later date) |
| `Plural-Forms` header | nplurals=3 | unchanged | **auto-merged** (nplurals=3) |

## Conflict policy

Conflicts are never resolved by picking a side: conflicted messages in
`merged.po` keep the *base* translation and are marked `fuzzy`, and
`merge_catalogs` returns a structured `MergeConflict` list carrying the
base/ours/theirs values so a human (or a UI) can decide. When there are
no conflicts, the merged catalog can be written out and read back
unchanged.
