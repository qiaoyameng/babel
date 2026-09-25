"""
babel.messages.checkers
~~~~~~~~~~~~~~~~~~~~~~~

Various routines that help with validation of translations.

:since: version 0.9

:copyright: (c) 2013-2026 by the Babel Team.
:license: BSD, see LICENSE for more details.
"""

from __future__ import annotations

from collections.abc import Callable
from string import Formatter
from typing import TYPE_CHECKING

from babel.messages.catalog import PYTHON_FORMAT, Catalog, Message, TranslationError

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    _BraceFieldKey: TypeAlias = tuple[
        int | str,
        tuple[tuple[str, int | str], ...],
    ]

#: list of format chars that are compatible to each other
_string_format_compatibilities = [
    {'i', 'd', 'u'},
    {'x', 'X'},
    {'f', 'F', 'g', 'G'},
]

#: list of brace format type chars that are compatible to each other
_brace_format_compatibilities = [
    {'b', 'c', 'd', 'o', 'x', 'X', 'n'},
    {'e', 'E', 'f', 'F', 'g', 'G', '%'},
    {'', 's'},
]

#: all type chars known to the brace format mini-language
_brace_format_types = frozenset().union(*_brace_format_compatibilities)


def num_plurals(catalog: Catalog | None, message: Message) -> None:
    """Verify the number of plurals in the translation."""
    if not message.pluralizable:
        if not isinstance(message.string, str):
            raise TranslationError("Found plural forms for non-pluralizable message")
        return

    # skip further tests if no catalog is provided.
    elif catalog is None:
        return

    msgstrs = message.string
    if not isinstance(msgstrs, (list, tuple)):
        msgstrs = (msgstrs,)
    if len(msgstrs) != catalog.num_plurals:
        raise TranslationError(
            f"Wrong number of plural forms (expected {catalog.num_plurals})",
        )


def python_format(catalog: Catalog | None, message: Message) -> None:
    """Verify the format string placeholders in the translation."""
    if 'python-format' not in message.flags:
        return
    msgids = message.id
    if not isinstance(msgids, (list, tuple)):
        msgids = (msgids,)
    msgstrs = message.string
    if not isinstance(msgstrs, (list, tuple)):
        msgstrs = (msgstrs,)

    if msgstrs[0]:
        _validate_format(msgids[0], msgstrs[0])
    if message.pluralizable:
        for msgstr in msgstrs[1:]:
            if msgstr:
                _validate_format(msgids[1], msgstr)


def _validate_format(format: str, alternative: str) -> None:
    """Test format string `alternative` against `format`.  `format` can be the
    msgid of a message and `alternative` one of the `msgstr`\\s.  The two
    arguments are not interchangeable as `alternative` may contain less
    placeholders if `format` uses named placeholders.

    If the string formatting of `alternative` is compatible to `format` the
    function returns `None`, otherwise a `TranslationError` is raised.

    Examples for compatible format strings:

    >>> _validate_format('Hello %s!', 'Hallo %s!')
    >>> _validate_format('Hello %i!', 'Hallo %d!')

    Example for an incompatible format strings:

    >>> _validate_format('Hello %(name)s!', 'Hallo %s!')
    Traceback (most recent call last):
      ...
    TranslationError: the format strings are of different kinds

    This function is used by the `python_format` checker.

    :param format: The original format string
    :param alternative: The alternative format string that should be checked
                        against format
    :raises TranslationError: on formatting errors
    """

    def _parse(string: str) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for match in PYTHON_FORMAT.finditer(string):
            name, format, typechar = match.groups()
            if typechar == '%' and name is None:
                continue
            result.append((name, str(typechar)))
        return result

    def _compatible(a: str, b: str) -> bool:
        if a == b:
            return True
        for set in _string_format_compatibilities:
            if a in set and b in set:
                return True
        return False

    def _check_positional(results: list[tuple[str, str]]) -> bool:
        positional = None
        for name, _char in results:
            if positional is None:
                positional = name is None
            else:
                if (name is None) != positional:
                    raise TranslationError(
                        'format string mixes positional and named placeholders',
                    )
        return bool(positional)

    a = _parse(format)
    b = _parse(alternative)

    if not a:
        return

    # now check if both strings are positional or named
    a_positional = _check_positional(a)
    b_positional = _check_positional(b)
    if a_positional and not b_positional and not b:
        raise TranslationError('placeholders are incompatible')
    elif a_positional != b_positional:
        raise TranslationError('the format strings are of different kinds')

    # if we are operating on positional strings both must have the
    # same number of format chars and those must be compatible
    if a_positional:
        if len(a) != len(b):
            raise TranslationError('positional format placeholders are unbalanced')
        for idx, ((_, first), (_, second)) in enumerate(zip(a, b)):
            if not _compatible(first, second):
                raise TranslationError(
                    f'incompatible format for placeholder {idx + 1:d}: '
                    f'{first!r} and {second!r} are not compatible',
                )

    # otherwise the second string must not have names the first one
    # doesn't have and the types of those included must be compatible
    else:
        type_map = dict(a)
        for name, typechar in b:
            if name not in type_map:
                raise TranslationError(f'unknown named placeholder {name!r}')
            elif not _compatible(typechar, type_map[name]):
                raise TranslationError(
                    f'incompatible format for placeholder {name!r}: '
                    f'{typechar!r} and {type_map[name]!r} are not compatible',
                )


def python_brace_format(catalog: Catalog | None, message: Message) -> None:
    """Verify the brace format string placeholders in the translation."""
    if 'python-brace-format' not in message.flags:
        return
    msgids = message.id
    if not isinstance(msgids, (list, tuple)):
        msgids = (msgids,)
    msgstrs = message.string
    if not isinstance(msgstrs, (list, tuple)):
        msgstrs = (msgstrs,)

    if message.pluralizable:
        for idx, msgstr in enumerate(msgstrs):
            if msgstr:
                msgid = msgids[0] if idx == 0 else msgids[1]
                try:
                    _validate_brace_format(msgid, msgstr)
                except TranslationError as e:
                    raise TranslationError(f'msgstr[{idx:d}]: {e}') from e
    elif msgstrs[0]:
        _validate_brace_format(msgids[0], msgstrs[0])


def _validate_brace_format(format: str, alternative: str) -> None:
    """Test brace format string `alternative` against `format`.  `format` can
    be the msgid of a message and `alternative` one of the `msgstr`\\s.  The
    two arguments are not interchangeable: the translation may reorder the
    placeholders, but it must not drop, add or alter any of them.

    If the brace formatting of `alternative` is compatible to `format` the
    function returns `None`, otherwise a `TranslationError` is raised.

    Examples for compatible format strings:

    >>> _validate_brace_format('Hello {name}!', 'Hallo {name}!')
    >>> _validate_brace_format('{0} {1}', '{1} {0}')
    >>> _validate_brace_format('{user.name!r:>{width}}', '{user.name!r:>{width}}')

    Examples for incompatible format strings:

    >>> _validate_brace_format('Hello {name}!', 'Hallo!')
    Traceback (most recent call last):
      ...
    TranslationError: missing placeholder(s): 'name'

    >>> _validate_brace_format('{0:d}', '{0:s}')
    Traceback (most recent call last):
      ...
    TranslationError: incompatible format for placeholder '0': 's' and 'd' are not compatible

    This function is used by the `python_brace_format` checker.

    :param format: The original format string
    :param alternative: The alternative format string that should be checked
                        against format
    :raises TranslationError: on formatting errors
    """

    def _compatible(a: str, b: str) -> bool:
        if a == b:
            return True
        for compatibility in _brace_format_compatibilities:
            if a in compatibility and b in compatibility:
                return True
        return False

    a = _parse_brace_format(format)
    b = _parse_brace_format(alternative)

    if not a:
        return

    missing = sorted((key for key in a if key not in b), key=_brace_field_name)
    if missing:
        names = ', '.join(repr(_brace_field_name(key)) for key in missing)
        raise TranslationError(f'missing placeholder(s): {names}')
    unknown = sorted((key for key in b if key not in a), key=_brace_field_name)
    if unknown:
        names = ', '.join(repr(_brace_field_name(key)) for key in unknown)
        raise TranslationError(f'unknown placeholder(s): {names}')

    for key, specs in a.items():
        name = _brace_field_name(key)
        conversion, type_char = specs[0]
        for alt_conversion, alt_type_char in b[key]:
            if alt_conversion != conversion:
                raise TranslationError(
                    f'conversion for placeholder {name!r} changed '
                    f'from {conversion!r} to {alt_conversion!r}',
                )
            if not _compatible(alt_type_char, type_char):
                raise TranslationError(
                    f'incompatible format for placeholder {name!r}: '
                    f'{alt_type_char!r} and {type_char!r} are not compatible',
                )


def _parse_brace_format(string: str) -> dict[_BraceFieldKey, list[tuple[str, str]]]:
    """Parse a brace format string into a mapping of placeholder keys to
    lists of ``(conversion, type_char)`` tuples, one per occurrence of the
    placeholder.  Placeholders nested within format specs are included.
    """
    fields: dict[_BraceFieldKey, list[tuple[str, str]]] = {}
    formatter = Formatter()
    automatic_numbering = False
    manual_numbering = False
    auto_index = 0

    def _parse(string: str) -> str:
        nonlocal automatic_numbering, manual_numbering, auto_index
        try:
            # `parse` is a generator; consume it eagerly to catch
            # malformed format strings here
            chunks = list(formatter.parse(string))
        except ValueError as exc:
            raise TranslationError(f'invalid brace format string: {exc}') from None
        literal_texts = []
        for literal_text, field_name, format_spec, conversion in chunks:
            literal_texts.append(literal_text)
            if field_name is None:
                continue
            if '{' in format_spec or '}' in format_spec:
                # placeholders nested in the format spec reference arguments
                # as well; parse them and keep the remaining literal spec
                bare_spec = _parse(format_spec)
            else:
                bare_spec = format_spec
            if field_name == '':
                automatic_numbering = True
                key: _BraceFieldKey = (auto_index, ())
                auto_index += 1
            else:
                root, path = _split_brace_field_name(field_name)
                if isinstance(root, int):
                    manual_numbering = True
                key = (root, path)
            fields.setdefault(key, []).append((conversion or '', _brace_type_char(bare_spec)))
        return ''.join(literal_texts)

    _parse(string)
    if automatic_numbering and manual_numbering:
        raise TranslationError(
            'format string mixes automatic and explicit argument numbering',
        )
    return fields


def _split_brace_field_name(field_name: str) -> _BraceFieldKey:
    """Split a brace format field name into the root argument and the
    attribute/item access path.

    >>> _split_brace_field_name('user.addresses[0].street')
    ('user', (('attr', 'addresses'), ('item', 0), ('attr', 'street')))
    >>> _split_brace_field_name('0')
    (0, ())
    """
    for pos, char in enumerate(field_name):
        if char in '.[':
            break
    else:
        pos = len(field_name)
    root: int | str = field_name[:pos]
    if root.isdigit():
        root = int(root)
    path = []
    rest = field_name[pos:]
    while rest:
        if rest.startswith('.'):
            end = len(rest)
            for idx, char in enumerate(rest[1:], 1):
                if char in '.[':
                    end = idx
                    break
            path.append(('attr', rest[1:end]))
            rest = rest[end:]
        elif rest.startswith('['):
            end = rest.find(']')
            if end == -1:
                path.append(('item', rest))
                break
            item: int | str = rest[1:end]
            if item.isdigit():
                item = int(item)
            path.append(('item', item))
            rest = rest[end + 1:]
        else:
            path.append(('item', rest))
            break
    return root, tuple(path)


def _brace_type_char(bare_spec: str) -> str:
    """Extract the presentation type char from a brace format spec that has
    been stripped of nested placeholders.  Specs that look like date/time
    format strings (e.g. ``%Y-%m-%d``) yield no type char.
    """
    if not bare_spec or '%' in bare_spec[:-1]:
        return ''
    if bare_spec[-1] in _brace_format_types:
        return bare_spec[-1]
    return ''


def _brace_field_name(key: _BraceFieldKey) -> str:
    """Render a placeholder key back into a readable field name."""
    root, path = key
    parts = [str(root)]
    for kind, value in path:
        if kind == 'attr':
            parts.append(f'.{value}')
        else:
            parts.append(f'[{value}]')
    return ''.join(parts)


def _find_checkers() -> list[Callable[[Catalog | None, Message], object]]:
    from babel.messages._compat import find_entrypoints

    checkers: list[Callable[[Catalog | None, Message], object]] = []
    checkers.extend(load() for (name, load) in find_entrypoints('babel.checkers'))
    if len(checkers) == 0:
        # if entrypoints are not available or no usable egg-info was found
        # (see #230), just resort to hard-coded checkers
        return [num_plurals, python_format, python_brace_format]
    return checkers


checkers: list[Callable[[Catalog | None, Message], object]] = _find_checkers()
