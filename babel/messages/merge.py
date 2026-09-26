"""
babel.messages.merge
~~~~~~~~~~~~~~~~~~~~

Three-way merge for message catalogs.

Given a common ancestor catalog ("base") and two diverged revisions of it
("ours" and "theirs"), :func:`merge_catalogs` produces a merged catalog plus
a structured list of conflicts.

Messages are aligned by message ID and context (``msgctxt``), never by
position, and the merge is performed per message and per field -- never by
picking one whole file over the other:

* if one side changed the translation and the other side changed comments,
  flags or locations, both changes are merged automatically;
* if both sides changed the same translation to different values, a
  conflict is recorded and the merged catalog keeps the base translation
  (marked fuzzy) instead of arbitrarily picking either side;
* plural translations whose array length changed, delete-vs-modify edits,
  resurrected obsolete messages and header metadata are each handled
  separately.

:copyright: (c) 2013-2026 by the Babel Team.
:license: BSD, see LICENSE for more details.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from babel.messages.catalog import Catalog, Message

if TYPE_CHECKING:
    from babel.messages.catalog import _MessageID

#: Kinds of conflicts reported by :func:`merge_catalogs`.
ConflictKind = Literal[
    'translation',      # both sides changed the same translation differently
    'plural-length',    # plural translation arrays of different lengths
    'delete-vs-modify',  # one side deleted a message the other side modified
    'header',           # both sides changed the same header field differently
]

_ENTRY_ACTIVE = 'active'
_ENTRY_OBSOLETE = 'obsolete'
_ENTRY_ABSENT = 'absent'


@dataclass
class MergeConflict:
    """A single conflict found while merging two catalog revisions.

    ``id`` and ``context`` identify the conflicting message; both are
    ``None`` for header conflicts, in which case ``field`` names the
    catalog attribute that could not be merged.  ``base``, ``ours`` and
    ``theirs`` carry the conflicting values (``Message`` objects for
    message conflicts, plain values for header conflicts; ``None`` when
    the message is absent on that side).
    """

    kind: ConflictKind
    id: _MessageID | None = None
    context: str | None = None
    field: str | None = None
    base: Any = None
    ours: Any = None
    theirs: Any = None
    description: str = ''

    def __str__(self) -> str:
        where = self.field if self.kind == 'header' else f'msgid {self.id!r}'
        if self.context is not None:
            where = f'{where} (msgctxt {self.context!r})'
        return f'[{self.kind}] {where}: {self.description}'


def _normalize_string(string: _MessageID | None) -> str | tuple[str, ...] | None:
    """Normalize a message string for comparison (lists become tuples)."""
    if isinstance(string, (list, tuple)):
        return tuple(string)
    return string


def _message_signature(message: Message) -> tuple:
    """A hashable snapshot of everything that defines a message's content.

    ``lineno`` is deliberately excluded: it refers to a position in a
    specific PO file and is meaningless across revisions.
    """
    return (
        message.id if isinstance(message.id, str) else tuple(message.id),
        _normalize_string(message.string),
        tuple(message.locations),
        frozenset(message.flags),
        tuple(message.auto_comments),
        tuple(message.user_comments),
        tuple(message.previous_id),
        message.context,
    )


def _entry_for(catalog: Catalog, key: str | tuple[str, str]) -> tuple[str, Message | None]:
    """Return the state of ``key`` in ``catalog`` as ``(status, message)``."""
    message = catalog._messages.get(key)
    if message is not None:
        return _ENTRY_ACTIVE, message
    message = catalog.obsolete.get(key)
    if message is not None:
        return _ENTRY_OBSOLETE, message
    return _ENTRY_ABSENT, None


def _entries_equal(a: tuple[str, Message | None], b: tuple[str, Message | None]) -> bool:
    if a[0] != b[0]:
        return False
    if a[1] is None:
        return True
    return _message_signature(a[1]) == _message_signature(b[1])


def _merge_collection(
    base: list, ours: list, theirs: list,
) -> list:
    """Three-way merge of ordered collections (locations, comments).

    Items removed by either side stay removed; items added by either side
    are kept, base items first (in base order), then additions from ours,
    then additions from theirs.
    """
    result = [item for item in base if item in ours or item in theirs]
    for item in ours:
        if item not in base and item not in result:
            result.append(item)
    for item in theirs:
        if item not in base and item not in result:
            result.append(item)
    return result


def _merge_message(
    key: str | tuple[str, str],
    base: Message | None,
    ours: Message,
    theirs: Message,
    conflicts: list[MergeConflict],
) -> Message:
    """Field-level three-way merge of two diverged versions of a message.

    ``base`` may be ``None`` when the message was added on both sides.
    Conflicting translations are never silently resolved: the merged
    message keeps the base translation (or an empty one), is marked fuzzy,
    and a :class:`MergeConflict` is appended to ``conflicts``.
    """
    base_string = _normalize_string(base.string) if base is not None else None
    ours_string = _normalize_string(ours.string)
    theirs_string = _normalize_string(theirs.string)

    needs_fuzzy = False
    if base is not None:
        merged = base.clone()
    else:
        merged = Message(ours.id, context=ours.context)
        merged.string = '' if not isinstance(ours_string, tuple) else tuple(
            '' for _ in ours_string
        )
    merged.lineno = None

    # --- msgid itself (e.g. one side made it pluralizable) ---
    base_id = base.id if base is not None else None
    if ours.id == theirs.id:
        merged.id = ours.id
    elif ours.id == base_id:
        merged.id = theirs.id
    elif theirs.id == base_id:
        merged.id = ours.id
    else:
        conflicts.append(MergeConflict(
            kind='translation',
            id=ours.id,
            context=ours.context,
            field='id',
            base=base,
            ours=ours,
            theirs=theirs,
            description='both sides changed the message ID differently',
        ))
        needs_fuzzy = True

    # --- translation (msgstr) ---
    if ours_string == theirs_string:
        string = ours_string
    elif ours_string == base_string:
        string = theirs_string
    elif theirs_string == base_string:
        string = ours_string
    else:
        candidates = [s for s in (base_string, ours_string, theirs_string)
                      if isinstance(s, tuple)]
        kind: ConflictKind = 'translation'
        if candidates and len({len(s) for s in candidates}) > 1:
            kind = 'plural-length'
        conflicts.append(MergeConflict(
            kind=kind,
            id=ours.id,
            context=ours.context,
            field='string',
            base=base,
            ours=ours,
            theirs=theirs,
            description=(
                'plural translations have different numbers of forms'
                if kind == 'plural-length'
                else 'both sides changed the translation differently'
            ),
        ))
        # Do not pick either side: keep the base translation (or an empty
        # one for newly added messages) and mark the message fuzzy.
        string = base_string
        needs_fuzzy = True

    if string is None:
        string = '' if not isinstance(ours_string, tuple) else tuple(
            '' for _ in ours_string
        )
    if isinstance(string, tuple):
        merged.string = tuple(string)
    else:
        merged.string = string

    # --- locations, comments, flags: set-style merges never conflict ---
    base_locations = base.locations if base is not None else []
    merged.locations = _merge_collection(base_locations, ours.locations, theirs.locations)
    base_auto = base.auto_comments if base is not None else []
    merged.auto_comments = _merge_collection(base_auto, ours.auto_comments, theirs.auto_comments)
    base_user = base.user_comments if base is not None else []
    merged.user_comments = _merge_collection(base_user, ours.user_comments, theirs.user_comments)
    base_flags = base.flags if base is not None else set()
    merged.flags = (
        (base_flags & ours.flags & theirs.flags)
        | (ours.flags - base_flags)
        | (theirs.flags - base_flags)
    )
    if needs_fuzzy:
        merged.flags.add('fuzzy')

    # --- previous_id: scalar three-way, deterministic fallback ---
    base_previous = tuple(base.previous_id) if base is not None else ()
    if tuple(ours.previous_id) == tuple(theirs.previous_id):
        merged.previous_id = list(ours.previous_id)
    elif tuple(ours.previous_id) == base_previous:
        merged.previous_id = list(theirs.previous_id)
    elif tuple(theirs.previous_id) == base_previous:
        merged.previous_id = list(ours.previous_id)
    else:
        merged.previous_id = list(theirs.previous_id)

    return merged


def _merge_header_attributes(
    base: Catalog, ours: Catalog, theirs: Catalog,
    conflicts: list[MergeConflict],
) -> dict[str, Any]:
    """Three-way merge of catalog header metadata, attribute by attribute."""
    attributes = [
        'domain', 'project', 'version', 'copyright_holder',
        'msgid_bugs_address', 'last_translator', 'language_team', 'charset',
        'fuzzy', 'creation_date', 'revision_date', 'locale_identifier',
        'plural_forms_pair', '_header_comment',
    ]
    values: dict[str, Any] = {}
    for attr in attributes:
        if attr == 'plural_forms_pair':
            # nplurals and the plural expression form one logical header.
            getter = lambda c: (c._num_plurals, c._plural_expr)  # noqa: E731
        else:
            getter = lambda c, a=attr: getattr(c, a)  # noqa: E731
        base_value = getter(base)
        ours_value = getter(ours)
        theirs_value = getter(theirs)
        if ours_value == theirs_value:
            values[attr] = ours_value
        elif ours_value == base_value:
            values[attr] = theirs_value
        elif theirs_value == base_value:
            values[attr] = ours_value
        elif attr == 'revision_date' and all(
            isinstance(v, datetime.datetime)
            for v in (ours_value, theirs_value)
        ):
            # Both sides stamped a new revision date: the later one wins.
            values[attr] = max(ours_value, theirs_value)
        else:
            field = attr.lstrip('_')
            if attr == 'plural_forms_pair':
                field = 'Plural-Forms'
            elif attr == '_header_comment':
                field = 'header_comment'
            conflicts.append(MergeConflict(
                kind='header',
                field=field,
                base=base_value,
                ours=ours_value,
                theirs=theirs_value,
                description='both sides changed this header field differently',
            ))
            values[attr] = base_value

    # Flatten the plural-forms pair back into the individual attributes.
    if 'plural_forms_pair' in values:
        num_plurals, plural_expr = values.pop('plural_forms_pair')
        values['_num_plurals'] = num_plurals
        values['_plural_expr'] = plural_expr
    return values


def merge_catalogs(
    base: Catalog,
    ours: Catalog,
    theirs: Catalog,
) -> tuple[Catalog, list[MergeConflict]]:
    """Merge two diverged revisions of a message catalog.

    :param base: the common ancestor catalog
    :param ours: the first diverged revision
    :param theirs: the second diverged revision
    :return: a ``(merged_catalog, conflicts)`` tuple; when ``conflicts`` is
             empty the merged catalog is a clean, stable result that can be
             written out and read back unchanged.  When conflicts exist the
             affected messages keep their base translations and are marked
             fuzzy -- neither side's translation is used as the final one.
    """
    conflicts: list[MergeConflict] = []

    merged = Catalog()
    for attr, value in _merge_header_attributes(base, ours, theirs, conflicts).items():
        if attr == 'locale_identifier':
            merged.locale = value
        else:
            setattr(merged, attr, value)

    # Deterministic key order: base first, then additions from ours, then
    # additions from theirs, each in their own file order.
    keys: list[str | tuple[str, str]] = list(base._messages)
    keys += [key for key in base.obsolete if key not in keys]
    keys += [key for key in ours._messages if key not in keys]
    keys += [key for key in ours.obsolete if key not in keys]
    keys += [key for key in theirs._messages if key not in keys]
    keys += [key for key in theirs.obsolete if key not in keys]

    for key in keys:
        base_entry = _entry_for(base, key)
        ours_entry = _entry_for(ours, key)
        theirs_entry = _entry_for(theirs, key)

        ours_changed = not _entries_equal(base_entry, ours_entry)
        theirs_changed = not _entries_equal(base_entry, theirs_entry)

        if not ours_changed:
            status, message = theirs_entry
            result = (status, message.clone() if message else None)
        elif not theirs_changed:
            status, message = ours_entry
            result = (status, message.clone() if message else None)
        elif _entries_equal(ours_entry, theirs_entry):
            status, message = ours_entry
            result = (status, message.clone() if message else None)
        else:
            result = _merge_diverged(key, base_entry, ours_entry, theirs_entry, conflicts)

        status, message = result
        if status == _ENTRY_ACTIVE:
            merged._messages[key] = message
        elif status == _ENTRY_OBSOLETE:
            merged.obsolete[key] = message

    return merged, conflicts


def _merge_diverged(
    key: str | tuple[str, str],
    base_entry: tuple[str, Message | None],
    ours_entry: tuple[str, Message | None],
    theirs_entry: tuple[str, Message | None],
    conflicts: list[MergeConflict],
) -> tuple[str, Message | None]:
    """Merge one message key where both sides diverged from base."""
    base_status, base_msg = base_entry
    ours_status, ours_msg = ours_entry
    theirs_status, theirs_msg = theirs_entry

    if ours_status == _ENTRY_ACTIVE and theirs_status == _ENTRY_ACTIVE:
        return _ENTRY_ACTIVE, _merge_message(key, base_msg, ours_msg, theirs_msg, conflicts)

    if base_status == _ENTRY_ACTIVE:
        if ours_status == _ENTRY_ACTIVE or theirs_status == _ENTRY_ACTIVE:
            # One side deleted the message (or made it obsolete) while the
            # other side modified the active translation: delete-vs-modify.
            kept = ours_entry if ours_status == _ENTRY_ACTIVE else theirs_entry
            conflicts.append(MergeConflict(
                kind='delete-vs-modify',
                id=kept[1].id,
                context=kept[1].context,
                base=base_msg,
                ours=ours_msg,
                theirs=theirs_msg,
                description='one side deleted this message while the other modified it',
            ))
            # Keep the modified message (no data loss) but flag it for review.
            message = kept[1].clone()
            message.flags.add('fuzzy')
            return _ENTRY_ACTIVE, message
        # Both sides removed the active message; keep it obsolete if either
        # side did so, merging diverged obsolete copies field by field.
        if ours_status == _ENTRY_OBSOLETE and theirs_status == _ENTRY_OBSOLETE:
            return _ENTRY_OBSOLETE, _merge_message(key, base_msg, ours_msg, theirs_msg, conflicts)
        kept = ours_entry if ours_status == _ENTRY_OBSOLETE else theirs_entry
        if kept[0] == _ENTRY_OBSOLETE:
            return _ENTRY_OBSOLETE, kept[1].clone()
        return _ENTRY_ABSENT, None

    # Base was obsolete or absent.
    if ours_status == _ENTRY_ACTIVE or theirs_status == _ENTRY_ACTIVE:
        # An obsolete message was resurrected on one side (or added on
        # both).  Resurrection wins over removal so no data is lost.
        kept = ours_entry if ours_status == _ENTRY_ACTIVE else theirs_entry
        return _ENTRY_ACTIVE, kept[1].clone()

    if ours_status == _ENTRY_OBSOLETE and theirs_status == _ENTRY_OBSOLETE:
        return _ENTRY_OBSOLETE, _merge_message(key, base_msg, ours_msg, theirs_msg, conflicts)

    # One side purged the obsolete message, the other edited it: keep the
    # edited obsolete copy rather than losing it.
    kept = ours_entry if ours_status == _ENTRY_OBSOLETE else theirs_entry
    if kept[0] == _ENTRY_OBSOLETE:
        return _ENTRY_OBSOLETE, kept[1].clone()
    return _ENTRY_ABSENT, None
