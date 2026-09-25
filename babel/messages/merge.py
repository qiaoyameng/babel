"""
babel.messages.merge
~~~~~~~~~~~~~~~~~~~~

Three-way merge for message catalogs.

Given a common ancestor catalog and two divergent revisions (``ours`` and
``theirs``), :func:`merge_catalogs` produces a merged catalog together with a
structured list of conflicts that require a human decision.

Messages are aligned by their context (``msgctxt``) and message ID; the merge
works per message (and per message field), never on whole files.

* When one side changes the translation and the other side changes comments,
  locations or flags, both changes are combined automatically.
* When both sides change the same translation to different strings, the
  conflict is recorded; the ancestor text is kept and the message is marked
  fuzzy instead of picking a winner.
* Plural arrays are merged element-wise, so a change in the number of plural
  forms on one side is accepted automatically.
* Deletions are merged with modifications on the other side as
  delete-vs-modify conflicts.
* Obsolete messages can be revived; obsoleting versus modifying is reported
  separately.
* Catalog header metadata (MIME headers, fuzzy bit, plural forms ...) is
  merged field by field.

A merge without conflicts can be written to a PO file and read back without
loss; a merge with conflicts never silently treats either side as the final
translation.

:copyright: (c) 2026 by the Babel Team.
:license: BSD, see LICENSE for more details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from babel.messages.catalog import Catalog, Message

__all__ = [
    "DELETE_VS_MODIFY_CONFLICT",
    "HEADER_CONFLICT",
    "MESSAGE_ID_CONFLICT",
    "MergeConflict",
    "MergeResult",
    "OBSOLETE_VS_MODIFY_CONFLICT",
    "PLURAL_LENGTH_CONFLICT",
    "PREVIOUS_ID_CONFLICT",
    "TRANSLATION_CONFLICT",
    "merge_catalogs",
]

#: Both sides changed the same translation to different strings.
TRANSLATION_CONFLICT = "translation"

#: Both sides changed the length of a plural translation array differently.
PLURAL_LENGTH_CONFLICT = "plural-length"

#: One side deleted a message that the other side modified.
DELETE_VS_MODIFY_CONFLICT = "delete-vs-modify"

#: One side obsoleted a message that the other side modified.
OBSOLETE_VS_MODIFY_CONFLICT = "obsolete-vs-modify"

#: Both sides changed the message ID (including the plural form) differently.
MESSAGE_ID_CONFLICT = "message-id"

#: Both sides changed the previous (fuzzy-matched) message ID differently.
PREVIOUS_ID_CONFLICT = "previous-id"

#: Both sides changed the same header metadata field differently.
HEADER_CONFLICT = "header"


@dataclass
class MergeConflict:
    """A single conflict that requires a human decision.

    :param kind: one of the ``*_CONFLICT`` constants in this module
    :param id: the message ID (singular string, plural tuple, or ``None``
               for header conflicts)
    :param context: the message context (``msgctxt``), or ``None``
    :param base: the value as found in the common ancestor
    :param ours: the value as found in ``ours``
    :param theirs: the value as found in ``theirs``
    :param message: the :class:`~babel.messages.catalog.Message` placed in the
                    merged catalog (kept fuzzy with the ancestor translation),
                    or ``None`` for header conflicts
    :param detail: a short human-readable description of what conflicts
    """

    kind: str
    id: "str | tuple[str, ...] | None"
    context: "str | None" = None
    base: Any = None
    ours: Any = None
    theirs: Any = None
    message: "Message | None" = None
    detail: str = ""

    @property
    def is_header(self) -> bool:
        """Whether the conflict concerns catalog header metadata."""
        return self.kind == HEADER_CONFLICT

    def __str__(self) -> str:
        if self.is_header:
            return f"[{self.kind}] header field {self.detail!r}: ours={self.ours!r}, theirs={self.theirs!r}"
        if self.context is not None:
            target = f"{self.context!r}:{self.id!r}"
        else:
            target = repr(self.id)
        return f"[{self.kind}] message {target}: {self.detail}"


@dataclass
class MergeResult:
    """The outcome of a three-way catalog merge."""

    #: The merged catalog. Messages involved in a conflict are kept fuzzy and
    #: retain their ancestor translation instead of picking a side.
    catalog: Catalog

    #: Structured list of conflicts that require a human decision.
    conflicts: "list[MergeConflict]" = field(default_factory=list)

    #: Messages that were changed on both sides but could be combined without
    #: conflict (e.g. translation from one side, comments from the other).
    auto_merged: "list[Message]" = field(default_factory=list)

    @property
    def has_conflicts(self) -> bool:
        """Whether any conflicts require a human decision."""
        return bool(self.conflicts)

    @property
    def ok(self) -> bool:
        """Whether the merge produced no conflicts."""
        return not self.conflicts

    def conflicts_for(
        self,
        id: "str | tuple[str, ...]",
        context: "str | None" = None,
    ) -> "list[MergeConflict]":
        """Return all conflicts recorded for the given message ID."""
        return [
            conflict
            for conflict in self.conflicts
            if conflict.id == id and conflict.context == context
        ]


def merge_catalogs(
    base: Catalog,
    ours: Catalog,
    theirs: Catalog,
) -> MergeResult:
    """Merge two divergent revisions of a catalog against a common ancestor.

    >>> from babel.messages import Catalog
    >>> base = Catalog(locale='de')
    >>> base.add('Save', 'Speichern', locations=[('app.py', 1)])
    <Message ...>
    >>> ours = Catalog(locale='de')
    >>> ours.add('Save', 'Sichern', locations=[('app.py', 1)])
    <Message ...>
    >>> theirs = Catalog(locale='de')
    >>> theirs.add('Save', 'Speichern', locations=[('app.py', 2)])
    <Message ...>
    >>> result = merge_catalogs(base, ours, theirs)
    >>> result.ok
    True
    >>> message = result.catalog['Save']
    >>> message.string, message.locations
    ('Sichern', [('app.py', 2)])

    A change of the translation on one side and of the locations on the
    other side is combined automatically, while a translation changed on
    both sides produces a conflict and keeps the ancestor string:

    >>> theirs2 = Catalog(locale='de')
    >>> theirs2.add('Save', 'Ablegen', locations=[('app.py', 1)])
    <Message ...>
    >>> result = merge_catalogs(base, ours, theirs2)
    >>> result.ok
    False
    >>> conflict = result.conflicts[0]
    >>> conflict.kind, conflict.ours, conflict.theirs
    ('translation', 'Sichern', 'Ablegen')
    >>> message = result.catalog['Save']
    >>> message.string, message.fuzzy
    ('Speichern', True)

    :param base: the common ancestor catalog
    :param ours: one divergent revision of the catalog
    :param theirs: the other divergent revision of the catalog
    :return: a :class:`MergeResult` with the merged catalog and the
             structured conflict list
    """
    conflicts: list[MergeConflict] = []
    auto_merged: list[Message] = []

    catalog = _merge_headers(base, ours, theirs, conflicts)
    _merge_messages(base, ours, theirs, catalog, conflicts, auto_merged)

    return MergeResult(catalog=catalog, conflicts=conflicts, auto_merged=auto_merged)


# ---------------------------------------------------------------------------
# Header metadata
# ---------------------------------------------------------------------------

#: Catalog attributes that carry the PO header metadata. Each is merged
#: independently so a conflict on one field never forces a whole-file choice.
_HEADER_ATTRIBUTES = (
    "domain",
    "project",
    "version",
    "copyright_holder",
    "msgid_bugs_address",
    "last_translator",
    "language_team",
    "charset",
    "fuzzy",
    "_num_plurals",
    "_plural_expr",
    "_header_comment",
)

#: Date headers are merged by "latest wins" rather than by conflict: both
#: branches legitimately bump these timestamps, so flagging them would be
#: noise. Non-comparable values fall back to the regular three-way rule.
_DATE_ATTRIBUTES = ("creation_date", "revision_date")


def _merge_headers(
    base: Catalog,
    ours: Catalog,
    theirs: Catalog,
    conflicts: list[MergeConflict],
) -> Catalog:
    merged = Catalog()
    for attribute in _HEADER_ATTRIBUTES:
        base_value = getattr(base, attribute)
        ours_value = getattr(ours, attribute)
        theirs_value = getattr(theirs, attribute)
        value, status = _three_way(base_value, ours_value, theirs_value)
        if status == "conflict":
            conflicts.append(
                MergeConflict(
                    kind=HEADER_CONFLICT,
                    id=None,
                    base=base_value,
                    ours=ours_value,
                    theirs=theirs_value,
                    detail=attribute.lstrip("_"),
                ),
            )
        setattr(merged, attribute, value)

    for attribute in _DATE_ATTRIBUTES:
        setattr(
            merged,
            attribute,
            _merge_date(
                getattr(base, attribute),
                getattr(ours, attribute),
                getattr(theirs, attribute),
                conflicts,
                attribute,
            ),
        )

    locale_value, status = _three_way(
        base.locale_identifier,
        ours.locale_identifier,
        theirs.locale_identifier,
    )
    if status == "conflict":
        conflicts.append(
            MergeConflict(
                kind=HEADER_CONFLICT,
                id=None,
                base=base.locale_identifier,
                ours=ours.locale_identifier,
                theirs=theirs.locale_identifier,
                detail="locale",
            ),
        )
        locale_value = base.locale_identifier
    merged.locale = locale_value
    return merged


def _merge_date(base_value, ours_value, theirs_value, conflicts, attribute):
    value, status = _three_way(base_value, ours_value, theirs_value)
    if status != "conflict":
        return value
    try:
        return max(ours_value, theirs_value)
    except TypeError:
        conflicts.append(
            MergeConflict(
                kind=HEADER_CONFLICT,
                id=None,
                base=base_value,
                ours=ours_value,
                theirs=theirs_value,
                detail=attribute,
            ),
        )
        return base_value


def _three_way(base_value, ours_value, theirs_value):
    """Pick the changed side of a three-way comparison.

    Returns ``(value, status)`` where status is one of ``"same"``,
    ``"ours"``, ``"theirs"`` or ``"conflict"``. On conflict the base value
    is returned so nothing is silently picked.
    """
    if ours_value == theirs_value:
        return ours_value, "same"
    if base_value == ours_value:
        return theirs_value, "theirs"
    if base_value == theirs_value:
        return ours_value, "ours"
    return base_value, "conflict"


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

# A message "state" is a (message, is_obsolete) tuple; None means the message
# is absent from the catalog entirely.


def _state(catalog: Catalog, key) -> "tuple[Message, bool] | None":
    message = catalog._messages.get(key)
    if message is not None:
        return message, False
    message = catalog.obsolete.get(key)
    if message is not None:
        return message, True
    return None


def _messages_equivalent(left: Message, right: Message) -> bool:
    """Compare two messages on all fields relevant for merging.

    ``lineno`` is ignored: it is a parse-time artefact of a specific file,
    not catalog content.
    """
    return (
        left.id == right.id
        and left.string == right.string
        and left.locations == right.locations
        and left.flags == right.flags
        and left.auto_comments == right.auto_comments
        and left.user_comments == right.user_comments
        and left.previous_id == right.previous_id
        and left.context == right.context
    )


def _states_equivalent(left, right) -> bool:
    if left is None or right is None:
        return left is right
    return left[1] == right[1] and _messages_equivalent(left[0], right[0])


def _ordered_keys(*catalogs: Catalog) -> list:
    """All message keys across the catalogs, in deterministic order.

    Keys appear in the order of the ancestor catalog first, then keys only
    known to the other catalogs, so a conflict-free merge re-reads stably.
    """
    keys: list = []
    seen: set = set()
    for catalog in catalogs:
        for mapping in (catalog._messages, catalog.obsolete):
            for key in mapping:
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
    return keys


def _clone(message: Message) -> Message:
    cloned = message.clone()
    cloned.lineno = None
    return cloned


def _merge_messages(
    base: Catalog,
    ours: Catalog,
    theirs: Catalog,
    merged: Catalog,
    conflicts: list[MergeConflict],
    auto_merged: list[Message],
) -> None:
    for key in _ordered_keys(base, ours, theirs):
        base_state = _state(base, key)
        ours_state = _state(ours, key)
        theirs_state = _state(theirs, key)

        if _states_equivalent(ours_state, theirs_state):
            # Both sides agree (including: both deleted the message).
            _place(merged, key, ours_state)
            continue
        if _states_equivalent(base_state, ours_state):
            # Only theirs changed anything (add, modify, delete, revive).
            _place(merged, key, theirs_state)
            continue
        if _states_equivalent(base_state, theirs_state):
            # Only ours changed anything.
            _place(merged, key, ours_state)
            continue

        # Both sides changed the message in different ways.
        if ours_state is None or theirs_state is None:
            _resolve_delete_vs_modify(
                key, base_state, ours_state, theirs_state, merged, conflicts,
            )
        elif ours_state[1] != theirs_state[1]:
            _resolve_obsolete_vs_modify(
                key, base_state, ours_state, theirs_state, merged, conflicts,
            )
        else:
            message, message_conflicts = _merge_message_fields(
                base_state[0], ours_state[0], theirs_state[0],
            )
            obsolete = ours_state[1]
            stored = _place(merged, key, (message, obsolete))
            for conflict in message_conflicts:
                conflict.message = stored
            conflicts.extend(message_conflicts)
            if not message_conflicts:
                auto_merged.append(stored)


def _place(merged: Catalog, key, state) -> "Message | None":
    if state is None:
        return None
    message, obsolete = state
    stored = _clone(message)
    if obsolete:
        merged.obsolete[key] = stored
    else:
        merged._messages[key] = stored
    return stored


def _resolve_delete_vs_modify(
    key,
    base_state,
    ours_state,
    theirs_state,
    merged: Catalog,
    conflicts: list[MergeConflict],
) -> None:
    """One side deleted the message, the other side modified it.

    The modified message is kept (deleting would silently lose the other
    side's work) but marked fuzzy, and the conflict is recorded.
    """
    survivor = theirs_state if ours_state is None else ours_state
    message = _place(merged, key, survivor)
    message.flags.add("fuzzy")
    conflicts.append(
        MergeConflict(
            kind=DELETE_VS_MODIFY_CONFLICT,
            id=message.id,
            context=message.context,
            base=base_state[0] if base_state else None,
            ours=ours_state[0] if ours_state else None,
            theirs=theirs_state[0] if theirs_state else None,
            message=message,
            detail=(
                "deleted on one side, modified on the other; "
                "the modified message is kept fuzzy"
            ),
        ),
    )


def _resolve_obsolete_vs_modify(
    key,
    base_state,
    ours_state,
    theirs_state,
    merged: Catalog,
    conflicts: list[MergeConflict],
) -> None:
    """One side obsoleted the message, the other side modified it.

    The active (modified) message is kept fuzzy and the conflict recorded;
    obsoleting is treated like a deletion that keeps the text around.
    """
    active = ours_state if not ours_state[1] else theirs_state
    message = _place(merged, key, (active[0], False))
    message.flags.add("fuzzy")
    conflicts.append(
        MergeConflict(
            kind=OBSOLETE_VS_MODIFY_CONFLICT,
            id=message.id,
            context=message.context,
            base=base_state[0] if base_state else None,
            ours=ours_state[0],
            theirs=theirs_state[0],
            message=message,
            detail=(
                "obsoleted on one side, modified on the other; "
                "the modified message is kept fuzzy"
            ),
        ),
    )


# ---------------------------------------------------------------------------
# Field-level merging of a single message
# ---------------------------------------------------------------------------


def _merge_message_fields(
    base: Message,
    ours: Message,
    theirs: Message,
) -> "tuple[Message, list[MergeConflict]]":
    """Merge two divergent versions of one message field by field.

    Returns the merged message (never shared with the inputs) and a list of
    conflicts. On any conflict the message is marked fuzzy and the affected
    field keeps its ancestor value, so no side is treated as final.
    """
    merged = _clone(base)
    conflicts: list[MergeConflict] = []

    def conflict(kind, base_value, ours_value, theirs_value, detail):
        conflicts.append(
            MergeConflict(
                kind=kind,
                id=merged.id,
                context=merged.context,
                base=base_value,
                ours=ours_value,
                theirs=theirs_value,
                detail=detail,
            ),
        )

    # Message ID (only the plural form can differ, the singular is the key).
    merged.id, status = _three_way(base.id, ours.id, theirs.id)
    if status == "conflict":
        conflict(
            MESSAGE_ID_CONFLICT,
            base.id,
            ours.id,
            theirs.id,
            "message ID changed differently on both sides",
        )

    # Translation string(s).
    string, string_conflict = _merge_strings(
        base.string, ours.string, theirs.string,
    )
    merged.string = string
    if string_conflict is not None:
        kind, detail = string_conflict
        conflict(kind, base.string, ours.string, theirs.string, detail)

    # Locations and comments: when both sides changed them, take the union
    # (they are additive metadata, so combining never loses information).
    for attribute in ("locations", "auto_comments", "user_comments"):
        base_value = getattr(base, attribute)
        ours_value = getattr(ours, attribute)
        theirs_value = getattr(theirs, attribute)
        value, status = _three_way(base_value, ours_value, theirs_value)
        if status == "conflict":
            value = _ordered_union(ours_value, theirs_value)
        setattr(merged, attribute, list(value))

    # Flags: union on both-sides-changed as well.
    value, status = _three_way(base.flags, ours.flags, theirs.flags)
    if status == "conflict":
        value = ours.flags | theirs.flags
    merged.flags = set(value)

    # Previous message ID (fuzzy-match bookkeeping).
    merged.previous_id, status = _three_way(
        base.previous_id, ours.previous_id, theirs.previous_id,
    )
    if status == "conflict":
        conflict(
            PREVIOUS_ID_CONFLICT,
            base.previous_id,
            ours.previous_id,
            theirs.previous_id,
            "previous message ID changed differently on both sides",
        )
    merged.previous_id = list(merged.previous_id)

    if conflicts:
        merged.flags.add("fuzzy")
    return merged, conflicts


def _ordered_union(*sequences) -> list:
    """Union of sequences, keeping items in first-seen order."""
    result: list = []
    for sequence in sequences:
        for item in sequence:
            if item not in result:
                result.append(item)
    return result


def _merge_strings(
    base: "str | tuple[str, ...]",
    ours: "str | tuple[str, ...]",
    theirs: "str | tuple[str, ...]",
) -> "tuple[str | tuple[str, ...], tuple[str, str] | None]":
    """Merge translation strings, element-wise for plural arrays.

    Returns ``(string, conflict)`` where conflict is a ``(kind, detail)``
    tuple or ``None``. Plural arrays may change length on one side; the
    missing tail elements of the other sides are treated as absent, so a
    one-sided length change merges cleanly.
    """
    if not any(isinstance(value, (list, tuple)) for value in (base, ours, theirs)):
        value, status = _three_way(base, ours, theirs)
        if status == "conflict":
            return base, (
                TRANSLATION_CONFLICT,
                "translation changed differently on both sides",
            )
        return value, None

    base_items = _string_items(base)
    ours_items = _string_items(ours)
    theirs_items = _string_items(theirs)
    length = max(len(base_items), len(ours_items), len(theirs_items))

    merged_items: "list[str | None]" = []
    conflicted = False
    for index in range(length):
        base_item = base_items[index] if index < len(base_items) else None
        ours_item = ours_items[index] if index < len(ours_items) else None
        theirs_item = theirs_items[index] if index < len(theirs_items) else None
        value, status = _three_way(base_item, ours_item, theirs_item)
        if status == "conflict":
            conflicted = True
        merged_items.append(value)

    # Drop trailing slots that ended up absent (e.g. one side shortened the
    # array and the other side did not touch it).
    while merged_items and merged_items[-1] is None:
        merged_items.pop()

    if conflicted:
        if len(ours_items) != len(theirs_items):
            return base, (
                PLURAL_LENGTH_CONFLICT,
                "plural translation arrays changed length differently "
                f"(base: {len(base_items)}, ours: {len(ours_items)}, "
                f"theirs: {len(theirs_items)})",
            )
        return base, (
            TRANSLATION_CONFLICT,
            "plural translations changed differently on both sides",
        )
    return tuple(item if item is not None else "" for item in merged_items), None


def _string_items(string: "str | tuple[str, ...]") -> list:
    if isinstance(string, (list, tuple)):
        return list(string)
    return [string]
