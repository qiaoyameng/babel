"""
babel.messages.checkers
~~~~~~~~~~~~~~~~~~~~~~~

Various routines that help with validation of translations.

:since: version 0.9

:copyright: (c) 2013-2026 by the Babel Team.
:license: BSD, see LICENSE for more details.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from string import Formatter

from babel.messages.catalog import PYTHON_FORMAT, Catalog, Message, TranslationError

#: list of format chars that are compatible to each other
_string_format_compatibilities = [
    {'i', 'd', 'u'},
    {'x', 'X'},
    {'f', 'F', 'g', 'G'},
]

#: list of brace format presentation types that are compatible to each other
_brace_format_compatibilities = [
    {'b', 'c', 'd', 'o', 'x', 'X', 'n'},
    {'e', 'E', 'f', 'F', 'g', 'G', '%'},
]

#: all presentation types of the brace format syntax
_brace_format_types = frozenset('bcdeEfFgGnosxX%')


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

    if msgstrs[0]:
        _validate_brace_format(msgids[0], msgstrs[0])
    if message.pluralizable:
        for msgstr in msgstrs[1:]:
            if msgstr:
                _validate_brace_format(msgids[1], msgstr)


def _validate_brace_format(format: str, alternative: str) -> None:
    """Test brace format string `alternative` against `format`.  `format` can
    be the msgid of a message and `alternative` one of the `msgstr`\\s.  The
    two arguments are not interchangeable as `alternative` may use the
    placeholders of `format` in a different order.

    If the brace formatting of `alternative` is compatible to `format` the
    function returns `None`, otherwise a `TranslationError` is raised.

    Examples for compatible format strings:

    >>> _validate_brace_format('Hello {name}!', 'Hallo {name}!')
    >>> _validate_brace_format('{0} {1}', '{1} {0}')
    >>> _validate_brace_format('{0:d}', '{0:x}')

    Examples for incompatible format strings:

    >>> _validate_brace_format('Hello {name}!', 'Hallo!')
    Traceback (most recent call last):
      ...
    TranslationError: placeholder 'name' is missing in the translation

    >>> _validate_brace_format('{0!r}', '{0!s}')
    Traceback (most recent call last):
      ...
    TranslationError: placeholder '0' uses conversion '!s' but the original uses conversion '!r'

    This function is used by the `python_brace_format` checker.

    :param format: The original format string
    :param alternative: The alternative format string that should be checked
                        against format
    :raises TranslationError: on formatting errors
    """

    def _compatible(a: str | None, b: str | None) -> bool:
        if a == b:
            return True
        if a is None or b is None:
            # no explicit presentation type is only compatible to string
            # formatting
            return a in (None, 's') and b in (None, 's')
        for group in _brace_format_compatibilities:
            if a in group and b in group:
                return True
        return False

    def _field_map(
        fields: list[tuple[str, str | None, str | None]],
    ) -> dict[str, list[tuple[str | None, str | None]]]:
        result: dict[str, list[tuple[str | None, str | None]]] = {}
        for name, conversion, spec_type in fields:
            result.setdefault(name, []).append((conversion, spec_type))
        return result

    try:
        a = _field_map(_parse_brace_format(format))
    except ValueError:
        # the original string is not a valid format string, so there is
        # nothing to check the translation against
        return
    try:
        b = _field_map(_parse_brace_format(alternative))
    except ValueError as exc:
        raise TranslationError(f'invalid format string: {exc}') from exc

    for name in a:
        if name not in b:
            raise TranslationError(
                f'placeholder {name!r} is missing in the translation',
            )
    for name, usages in b.items():
        if name not in a:
            raise TranslationError(f'unknown placeholder {name!r}')
        conversions = {conversion for conversion, _ in a[name]}
        spec_types = {spec_type for _, spec_type in a[name]}
        for conversion, spec_type in usages:
            if conversion not in conversions:
                raise TranslationError(
                    f'placeholder {name!r} uses {_conversion_name(conversion)} '
                    f'but the original uses '
                    f'{"/".join(sorted(_conversion_name(c) for c in conversions))}',
                )
            if not any(_compatible(spec_type, other) for other in spec_types):
                raise TranslationError(
                    f'incompatible format for placeholder {name!r}: '
                    f'{spec_type!r} and {min(spec_types, key=repr)!r} '
                    f'are not compatible',
                )


def _conversion_name(conversion: str | None) -> str:
    """Return a human readable representation of a conversion character."""
    return f"conversion '!{conversion}'" if conversion else 'no conversion'


def _parse_brace_format(string: str) -> list[tuple[str, str | None, str | None]]:
    """Parse a brace format string into a list of placeholders.

    Each placeholder is represented by a ``(name, conversion, spec_type)``
    tuple, where `name` is the full field name (including attribute or item
    access, with automatic field numbering resolved), `conversion` is the
    conversion character (without the leading ``!``) or `None`, and
    `spec_type` is the presentation type character of the format spec or
    `None`.  Placeholders nested in format specs are included as well.

    :raises TranslationError: if automatic and manual field numbering are mixed
    :raises ValueError: if the string is not a valid format string
    """
    fields: list[tuple[str, str | None, str | None]] = []
    auto_index = 0
    numbering: str | None = None

    def _parse(string: str) -> None:
        nonlocal auto_index, numbering
        for _literal, field_name, format_spec, conversion in Formatter().parse(string):
            if field_name is None:
                continue
            # split off attribute and item access to find the argument
            root = re.split(r'[.\[]', field_name, maxsplit=1)[0]
            if not root:
                if numbering == 'manual':
                    raise TranslationError(
                        'cannot switch from manual field numbering '
                        'to automatic field numbering',
                    )
                numbering = 'auto'
                name = f'{auto_index}{field_name}'
                auto_index += 1
            elif root.isdigit():
                if numbering == 'auto':
                    raise TranslationError(
                        'cannot switch from automatic field numbering '
                        'to manual field numbering',
                    )
                numbering = 'manual'
                name = field_name
            else:
                name = field_name
            fields.append((name, conversion, _brace_spec_type(format_spec)))
            # placeholders may be nested in the format spec
            _parse(format_spec)

    _parse(string)
    return fields


def _brace_spec_type(format_spec: str) -> str | None:
    """Extract the presentation type character from a format spec."""
    # remove nested replacement fields
    spec = re.sub(r'\{[^{}]*\}', '', format_spec)
    if spec and spec[-1] in _brace_format_types:
        return spec[-1]
    return None


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
