#!/usr/bin/env python3
"""Demonstrate the three-way catalog merge in ``babel.messages.merge``.

Reads ``base.po`` (common ancestor), ``ours.po`` and ``theirs.po`` from this
directory, merges them, writes ``merged.po`` and prints a report of what was
merged automatically and what needs a human decision.

Run from the repository root:

    python misc/merge-demo/merge_demo.py
"""

import sys
from pathlib import Path

from babel.messages.merge import merge_catalogs
from babel.messages.pofile import read_po, write_po

HERE = Path(__file__).parent


def read(name):
    with (HERE / name).open('rb') as fileobj:
        return read_po(fileobj)


def main() -> int:
    result = merge_catalogs(read('base.po'), read('ours.po'), read('theirs.po'))

    output = HERE / 'merged.po'
    with output.open('wb') as fileobj:
        write_po(fileobj, result.catalog)

    print(f"Merged catalog written to {output}")
    print(f"  messages: {len(result.catalog)}, "
          f"obsolete: {len(result.catalog.obsolete)}")

    print("\n== Merged automatically (changed on both sides, no conflict) ==")
    if result.auto_merged:
        for message in result.auto_merged:
            print(f"  {message.id!r} -> {message.string!r}")
    else:
        print("  (none)")

    print("\n== Needs a human decision ==")
    if result.conflicts:
        for conflict in result.conflicts:
            print(f"  {conflict}")
            if conflict.kind == 'translation':
                print(f"      ours:   {conflict.ours!r}")
                print(f"      theirs: {conflict.theirs!r}")
                print(f"      kept:   {conflict.base!r} (fuzzy)")
    else:
        print("  (none)")

    return 1 if result.has_conflicts else 0


if __name__ == '__main__':
    sys.exit(main())
