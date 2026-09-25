Three-Way Catalog Merge
=======================

.. module:: babel.messages.merge

The merge module combines two divergent revisions of a catalog (for
example from two translation branches) against their common ancestor.
Messages are aligned by context and message ID, and the merge works per
message and per field: a translation changed on one side is combined with
comment or location changes from the other side, while conflicting
translations, delete-vs-modify situations, plural array length changes and
header metadata are reported as structured conflicts instead of picking
one file wholesale.

.. autofunction:: merge_catalogs

.. autoclass:: MergeResult
   :members:

.. autoclass:: MergeConflict
   :members:
