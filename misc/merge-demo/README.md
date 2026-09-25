# Three-way catalog merge demo

This directory shows how `babel.messages.merge.merge_catalogs` merges two
translation branches that both changed the same PO file, without ever
falling back to picking one whole file over the other.

## The scenario

`base.po` is the common ancestor of two branches:

* `ours.po` (branch A) retranslates "Hello, world!", "Goodbye" and the
  `menu`-context "View", adds a translator comment to "File", switches the
  locale to three plural forms (adding `msgstr[2]`), deletes "Doomed entry",
  revives the obsolete "Legacy entry", and bumps `Last-Translator` to Bob.
* `theirs.po` (branch B) adds a translator comment and a new location to
  "Hello, world!", retranslates "Goodbye" and "File", edits "Doomed entry",
  and updates `Language-Team` and `Last-Translator` (Carol).

## What the merge does

Run it with:

    python misc/merge-demo/merge_demo.py

It writes `merged.po` and prints a report.

Merged automatically (per message, per field):

* "Hello, world!": translation from A + comment/location from B.
* "File": comment from A + translation from B.
* `menu`-context "View": retranslation from A (aligned by context, not just
  msgid).
* The plural entry: the longer plural array from A is accepted, combined
  with the plural-forms header change.
* "Legacy entry": revived from obsolete by A.
* Header: `Language-Team` from B, latest `PO-Revision-Date`, `Plural-Forms`
  from A — each header field is merged on its own.

Needs a human decision (reported as structured `MergeConflict` objects, no
side is silently treated as final):

* "Goodbye": both branches translated it differently; the ancestor text is
  kept and the message is marked fuzzy.
* "Doomed entry": deleted by A, modified by B; the modified message is kept
  fuzzy.
* `Last-Translator`: changed to different people on both sides; the ancestor
  value is kept.
