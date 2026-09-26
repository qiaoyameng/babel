"""Demo: three-way merge of two translation branches with Babel.

Reads ``base.po`` (common ancestor), ``ours.po`` and ``theirs.po`` from
this directory, merges them with :func:`babel.messages.merge.merge_catalogs`,
writes ``merged.po`` and prints a report of what was merged automatically
and what needs a human decision.

Run from the repository root:

    python misc/three-way-merge/run_merge.py
"""

from __future__ import annotations

import pathlib

from babel.messages.merge import merge_catalogs
from babel.messages.pofile import read_po, write_po

HERE = pathlib.Path(__file__).parent


def read(name):
    with open(HERE / name, encoding='utf-8') as f:
        return read_po(f, locale='de')


def main():
    base, ours, theirs = read('base.po'), read('ours.po'), read('theirs.po')
    merged, conflicts = merge_catalogs(base, ours, theirs)

    out = HERE / 'merged.po'
    with open(out, 'wb') as f:
        write_po(f, merged, omit_header=False)

    conflicted_keys = {(c.id if not isinstance(c.id, tuple) else c.id[0], c.context)
                       for c in conflicts if c.kind != 'header'}

    print('== Automatically merged ==')
    for message in merged:
        if not message.id:
            continue
        key = (message.id if isinstance(message.id, str) else message.id[0],
               message.context)
        marker = 'CONFLICT' if key in conflicted_keys else 'ok'
        if marker == 'ok':
            print(f'  {message.id!r} (ctxt={message.context!r}): {message.string!r}')

    print()
    print('== Needs a human ==')
    for conflict in conflicts:
        print(f'  {conflict}')
        if conflict.kind in ('translation', 'plural-length'):
            ours_s = conflict.ours.string if conflict.ours else None
            theirs_s = conflict.theirs.string if conflict.theirs else None
            print(f'    ours:   {ours_s!r}')
            print(f'    theirs: {theirs_s!r}')
    print()
    print(f'Merged catalog written to {out}')
    print('Conflicted messages keep the base translation and are marked fuzzy.')


if __name__ == '__main__':
    main()
