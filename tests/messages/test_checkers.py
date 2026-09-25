#
# Copyright (C) 2007-2011 Edgewall Software, 2013-2025 the Babel team
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at https://github.com/python-babel/babel/blob/master/LICENSE.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at https://github.com/python-babel/babel/commits/master/.

import re
from datetime import datetime
from io import BytesIO

import pytest

from babel import __version__ as VERSION
from babel.core import Locale, UnknownLocaleError
from babel.dates import format_datetime
from babel.messages import Message, checkers
from babel.messages.catalog import Catalog, TranslationError
from babel.messages.checkers import (
    _validate_brace_format,
    _validate_format,
    python_brace_format,
    python_format,
)
from babel.messages.plurals import PLURALS
from babel.messages.pofile import read_po
from babel.util import LOCALTZ

# the last msgstr[idx] is always missing except for singular plural forms


def test_1_num_plurals_checkers():
    for _locale in [p for p in PLURALS if PLURALS[p][0] == 1]:
        try:
            locale = Locale.parse(_locale)
        except UnknownLocaleError:
            # Just an alias? Not what we're testing here, let's continue
            continue
        date = format_datetime(datetime.now(LOCALTZ), 'yyyy-MM-dd HH:mmZ', tzinfo=LOCALTZ, locale=_locale)
        plural = PLURALS[_locale][0]
        po_file = (f"""\
# {locale.english_name} translations for TestProject.
# Copyright (C) 2007 FooBar, Inc.
# This file is distributed under the same license as the TestProject
# project.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2007.
#
msgid ""
msgstr ""
"Project-Id-Version: TestProject 0.1\\n"
"Report-Msgid-Bugs-To: bugs.address@email.tld\\n"
"POT-Creation-Date: 2007-04-01 15:30+0200\\n"
"PO-Revision-Date: {date}\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: {_locale} <LL@li.org>\n"
"Plural-Forms: nplurals={plural}; plural={plural};\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=utf-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Generated-By: Babel {VERSION}\\n"

#. This will be a translator comment,
#. that will include several lines
#: project/file1.py:8
msgid "bar"
msgstr ""

#: project/file2.py:9
msgid "foobar"
msgid_plural "foobars"
msgstr[0] ""

""").encode('utf-8')

        # This test will fail for revisions <= 406 because so far
        # catalog.num_plurals was neglected
        catalog = read_po(BytesIO(po_file), _locale)
        message = catalog['foobar']
        checkers.num_plurals(catalog, message)


def test_2_num_plurals_checkers():
    # in this testcase we add an extra msgstr[idx], we should be
    # disregarding it
    for _locale in [p for p in PLURALS if PLURALS[p][0] == 2]:
        if _locale in ['nn', 'no']:
            _locale = 'nn_NO'
            num_plurals = PLURALS[_locale.split('_')[0]][0]
            plural_expr = PLURALS[_locale.split('_')[0]][1]
        else:
            num_plurals = PLURALS[_locale][0]
            plural_expr = PLURALS[_locale][1]
        try:
            locale = Locale(_locale)
            date = format_datetime(datetime.now(LOCALTZ),
                                   'yyyy-MM-dd HH:mmZ',
                                   tzinfo=LOCALTZ, locale=_locale)
        except UnknownLocaleError:
            # Just an alias? Not what we're testing here, let's continue
            continue
        po_file = f"""\
# {locale.english_name} translations for TestProject.
# Copyright (C) 2007 FooBar, Inc.
# This file is distributed under the same license as the TestProject
# project.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2007.
#
msgid ""
msgstr ""
"Project-Id-Version: TestProject 0.1\\n"
"Report-Msgid-Bugs-To: bugs.address@email.tld\\n"
"POT-Creation-Date: 2007-04-01 15:30+0200\\n"
"PO-Revision-Date: {date}\\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"
"Language-Team: {_locale} <LL@li.org>\\n"
"Plural-Forms: nplurals={num_plurals}; plural={plural_expr};\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=utf-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Generated-By: Babel {VERSION}\\n"

#. This will be a translator comment,
#. that will include several lines
#: project/file1.py:8
msgid "bar"
msgstr ""

#: project/file2.py:9
msgid "foobar"
msgid_plural "foobars"
msgstr[0] ""
msgstr[1] ""
msgstr[2] ""

""".encode('utf-8')
        # we should be adding the missing msgstr[0]

        # This test will fail for revisions <= 406 because so far
        # catalog.num_plurals was neglected
        catalog = read_po(BytesIO(po_file), _locale)
        message = catalog['foobar']
        checkers.num_plurals(catalog, message)


def test_3_num_plurals_checkers():
    for _locale in [p for p in PLURALS if PLURALS[p][0] == 3]:
        plural = format_datetime(datetime.now(LOCALTZ), 'yyyy-MM-dd HH:mmZ', tzinfo=LOCALTZ, locale=_locale)
        english_name = Locale.parse(_locale).english_name
        po_file = rf"""\
# {english_name} translations for TestProject.
# Copyright (C) 2007 FooBar, Inc.
# This file is distributed under the same license as the TestProject
# project.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2007.
#
msgid ""
msgstr ""
"Project-Id-Version: TestProject 0.1\n"
"Report-Msgid-Bugs-To: bugs.address@email.tld\n"
"POT-Creation-Date: 2007-04-01 15:30+0200\n"
"PO-Revision-Date: {plural}\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: {_locale} <LL@li.org>\n"
"Plural-Forms: nplurals={PLURALS[_locale][0]}; plural={PLURALS[_locale][0]};\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Generated-By: Babel {VERSION}\n"

#. This will be a translator comment,
#. that will include several lines
#: project/file1.py:8
msgid "bar"
msgstr ""

#: project/file2.py:9
msgid "foobar"
msgid_plural "foobars"
msgstr[0] ""
msgstr[1] ""

""".encode('utf-8')

        # This test will fail for revisions <= 406 because so far
        # catalog.num_plurals was neglected
        catalog = read_po(BytesIO(po_file), _locale)
        message = catalog['foobar']
        checkers.num_plurals(catalog, message)


def test_4_num_plurals_checkers():
    for _locale in [p for p in PLURALS if PLURALS[p][0] == 4]:
        date = format_datetime(datetime.now(LOCALTZ), 'yyyy-MM-dd HH:mmZ', tzinfo=LOCALTZ, locale=_locale)
        english_name = Locale.parse(_locale).english_name
        plural = PLURALS[_locale][0]
        po_file = rf"""\
# {english_name} translations for TestProject.
# Copyright (C) 2007 FooBar, Inc.
# This file is distributed under the same license as the TestProject
# project.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2007.
#
msgid ""
msgstr ""
"Project-Id-Version: TestProject 0.1\n"
"Report-Msgid-Bugs-To: bugs.address@email.tld\n"
"POT-Creation-Date: 2007-04-01 15:30+0200\n"
"PO-Revision-Date: {date}\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: {_locale} <LL@li.org>\n"
"Plural-Forms: nplurals={plural}; plural={plural};\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Generated-By: Babel {VERSION}\n"

#. This will be a translator comment,
#. that will include several lines
#: project/file1.py:8
msgid "bar"
msgstr ""

#: project/file2.py:9
msgid "foobar"
msgid_plural "foobars"
msgstr[0] ""
msgstr[1] ""
msgstr[2] ""

""".encode('utf-8')

        # This test will fail for revisions <= 406 because so far
        # catalog.num_plurals was neglected
        catalog = read_po(BytesIO(po_file), _locale)
        message = catalog['foobar']
        checkers.num_plurals(catalog, message)


def test_5_num_plurals_checkers():
    for _locale in [p for p in PLURALS if PLURALS[p][0] == 5]:
        date = format_datetime(datetime.now(LOCALTZ), 'yyyy-MM-dd HH:mmZ', tzinfo=LOCALTZ, locale=_locale)
        english_name = Locale.parse(_locale).english_name
        plural = PLURALS[_locale][0]
        po_file = rf"""\
# {english_name} translations for TestProject.
# Copyright (C) 2007 FooBar, Inc.
# This file is distributed under the same license as the TestProject
# project.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2007.
#
msgid ""
msgstr ""
"Project-Id-Version: TestProject 0.1\n"
"Report-Msgid-Bugs-To: bugs.address@email.tld\n"
"POT-Creation-Date: 2007-04-01 15:30+0200\n"
"PO-Revision-Date: {date}\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: {_locale} <LL@li.org>\n"
"Plural-Forms: nplurals={plural}; plural={plural};\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Generated-By: Babel {VERSION}\n"

#. This will be a translator comment,
#. that will include several lines
#: project/file1.py:8
msgid "bar"
msgstr ""

#: project/file2.py:9
msgid "foobar"
msgid_plural "foobars"
msgstr[0] ""
msgstr[1] ""
msgstr[2] ""
msgstr[3] ""

""".encode('utf-8')

        # This test will fail for revisions <= 406 because so far
        # catalog.num_plurals was neglected
        catalog = read_po(BytesIO(po_file), _locale)
        message = catalog['foobar']
        checkers.num_plurals(catalog, message)


def test_6_num_plurals_checkers():
    for _locale in [p for p in PLURALS if PLURALS[p][0] == 6]:
        english_name = Locale.parse(_locale).english_name
        date = format_datetime(datetime.now(LOCALTZ), 'yyyy-MM-dd HH:mmZ', tzinfo=LOCALTZ, locale=_locale)
        plural = PLURALS[_locale][0]
        po_file = rf"""\
# {english_name} translations for TestProject.
# Copyright (C) 2007 FooBar, Inc.
# This file is distributed under the same license as the TestProject
# project.
# FIRST AUTHOR <EMAIL@ADDRESS>, 2007.
#
msgid ""
msgstr ""
"Project-Id-Version: TestProject 0.1\n"
"Report-Msgid-Bugs-To: bugs.address@email.tld\n"
"POT-Creation-Date: 2007-04-01 15:30+0200\n"
"PO-Revision-Date: {date}\n"
"Last-Translator: FULL NAME <EMAIL@ADDRESS>\n"
"Language-Team: {_locale} <LL@li.org>\n"
"Plural-Forms: nplurals={plural}; plural={plural};\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=utf-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Generated-By: Babel {VERSION}\n"

#. This will be a translator comment,
#. that will include several lines
#: project/file1.py:8
msgid "bar"
msgstr ""

#: project/file2.py:9
msgid "foobar"
msgid_plural "foobars"
msgstr[0] ""
msgstr[1] ""
msgstr[2] ""
msgstr[3] ""
msgstr[4] ""

""".encode('utf-8')

        # This test will fail for revisions <= 406 because so far
        # catalog.num_plurals was neglected
        catalog = read_po(BytesIO(po_file), _locale)
        message = catalog['foobar']
        checkers.num_plurals(catalog, message)


@pytest.mark.parametrize(
    ('msgid', 'msgstr'),
    [
        ('foo %s', 'foo'),
        (('foo %s', 'bar'), ('foo', 'bar')),
        (('foo', 'bar %s'), ('foo', 'bar')),
        (('foo %s', 'bar'), ('foo')),
        (('foo %s', 'bar %d'), ('foo %s', 'bar %d', 'baz')),
        (('foo %s', 'bar %d'), ('foo %s', 'bar %d', 'baz %d', 'qux')),
    ],
)
def test_python_format_invalid(msgid, msgstr):
    msg = Message(msgid, msgstr)
    with pytest.raises(TranslationError):
        python_format(None, msg)


@pytest.mark.parametrize(
    ('msgid', 'msgstr'),
    [
        ('foo', 'foo'),
        ('foo', 'foo %s'),
        ('foo %s', ''),
        (('foo %s', 'bar %d'), ('foo %s', 'bar %d')),
        (('foo %s', 'bar %d'), ('foo %s', 'bar %d', 'baz %d')),
        (('foo', 'bar %s'), ('foo')),
        (('foo', 'bar %s'), ('', '')),
        (('foo', 'bar %s'), ('foo', '')),
        (('foo %s', 'bar %d'), ('foo %s', '')),
    ],
)
def test_python_format_valid(msgid, msgstr):
    msg = Message(msgid, msgstr)
    python_format(None, msg)


@pytest.mark.parametrize(
    ('msgid', 'msgstr', 'error'),
    [
        ('%s %(foo)s', '%s %(foo)s', 'format string mixes positional and named placeholders'),
        ('foo %s', 'foo', 'placeholders are incompatible'),
        ('%s', '%(foo)s', 'the format strings are of different kinds'),
        ('%s', '%s %d', 'positional format placeholders are unbalanced'),
        ('%s', '%d', "incompatible format for placeholder 1: 's' and 'd' are not compatible"),
        (
            '%s %s %d',
            '%s %s %s',
            "incompatible format for placeholder 3: 'd' and 's' are not compatible",
        ),
        ('%(foo)s', '%(bar)s', "unknown named placeholder 'bar'"),
        ('%(foo)s', '%(bar)d', "unknown named placeholder 'bar'"),
        (
            '%(foo)s',
            '%(foo)d',
            "incompatible format for placeholder 'foo': 'd' and 's' are not compatible",
        ),
    ],
)
def test__validate_format_invalid(msgid, msgstr, error):
    with pytest.raises(TranslationError, match=error):
        _validate_format(msgid, msgstr)


@pytest.mark.parametrize(
    ('msgid', 'msgstr'),
    [
        ('foo', 'foo'),
        ('foo', 'foo %s'),
        ('%s foo', 'foo %s'),
        ('%i', '%d'),
        ('%d', '%u'),
        ('%x', '%X'),
        ('%f', '%F'),
        ('%F', '%g'),
        ('%g', '%G'),
        ('%(foo)s', 'foo'),
        ('%(foo)s', '%(foo)s %(foo)s'),
        ('%(bar)s foo %(n)d', '%(n)d foo %(bar)s'),
    ],
)
def test__validate_format_valid(msgid, msgstr):
    _validate_format(msgid, msgstr)


@pytest.mark.parametrize(
    ('msgid', 'msgstr'),
    [
        # placeholder dropped
        ('Hello {name}!', 'Hello!'),
        ('{0} {1}', '{0}'),
        # placeholder added
        ('Hello {name}!', 'Hello {name} {extra}!'),
        ('{0}', '{0} {1}'),
        # placeholder rewritten
        ('{user.name}', '{user.email}'),
        ('{0[0]}', '{0[1]}'),
        ('{items[0]}', '{items[1]}'),
        # nested placeholder in format spec dropped or rewritten
        ('{0:{width}}', '{0}'),
        ('{0:{width}}', '{0:{height}}'),
        # conversion changed
        ('{name!r}', '{name!s}'),
        ('{name!r}', '{name}'),
        ('{name}', '{name!a}'),
        # incompatible type formats
        ('{0:d}', '{0:s}'),
        ('{0:.2f}', '{0:.2d}'),
        # automatic and explicit numbering mixed
        ('{} {0}', '{} {0}'),
        ('{0}', '{} {0}'),
        # malformed translation
        ('{0}', '{0'),
        ('{0}', '}'),
        # plural messages: each translated form is checked
        (('one {thing}', 'many {things}'), ('one {thing}', 'many')),
        (('one {thing}', 'many {things}'), ('one', 'many {things}')),
    ],
)
def test_python_brace_format_invalid(msgid, msgstr):
    msg = Message(msgid, msgstr)
    assert 'python-brace-format' in msg.flags
    with pytest.raises(TranslationError):
        python_brace_format(None, msg)


@pytest.mark.parametrize(
    ('msgid', 'msgstr'),
    [
        ('Hello {name}!', 'Hallo {name}!'),
        # placeholders may be reordered
        ('{0} {1}', '{1} {0}'),
        ('{name} {other}', '{other} {name}'),
        # escaped braces are literal text
        ('{{literal}} {x}', '{{literal}} {x}'),
        # attribute and item access
        ('{user.name!r:>{width}}', '{user.name!r:>{width}}'),
        ('{0[1]:.2f}', '{0[1]:.2g}'),
        # compatible type formats
        ('{0:d}', '{0:x}'),
        ('{0:f}', '{0:g}'),
        # date/time format specs are not type formats
        ('{0:%Y-%m-%d}', '{0:%d.%m.%Y}'),
        # automatic numbering matches explicit positions
        ('{} {}', '{0} {1}'),
        # empty translations are skipped
        ('{0}', ''),
        (('one {thing}', 'many {things}'), ('', '')),
        (('one {thing}', 'many {things}'), ('one {thing}', '')),
        (('one {thing}', 'many {things}'), ('one {thing}', 'many {things}')),
    ],
)
def test_python_brace_format_valid(msgid, msgstr):
    msg = Message(msgid, msgstr)
    python_brace_format(None, msg)


def test_python_brace_format_plural_error_mentions_branch():
    msg = Message(('one {thing}', 'many {things}'), ('one {thing}', 'many'))
    with pytest.raises(TranslationError, match=r'msgstr\[1\]'):
        python_brace_format(None, msg)


def test_python_brace_format_catalog_check():
    catalog = Catalog(locale='en')
    catalog['Hello {name}!'] = Message('Hello {name}!', 'Hello!')
    catalog['{0} {1}'] = Message('{0} {1}', '{1} {0}')
    errors = list(catalog.check())
    assert len(errors) == 1
    message, message_errors = errors[0]
    assert message.id == 'Hello {name}!'
    assert "missing placeholder(s): 'name'" in str(message_errors[0])


@pytest.mark.parametrize(
    ('msgid', 'msgstr', 'error'),
    [
        ('{a} {b}', '{a}', "missing placeholder(s): 'b'"),
        ('{a}', '{a} {b}', "unknown placeholder(s): 'b'"),
        ('{0} {name}', '{name}', "missing placeholder(s): '0'"),
        ('{user.name}', '{user.name.first}', "missing placeholder(s): 'user.name'"),
        ('{name!r}', '{name!s}', "conversion for placeholder 'name' changed from 'r' to 's'"),
        ('{name}', '{name!r}', "conversion for placeholder 'name' changed from '' to 'r'"),
        ('{0:d}', '{0:f}', "incompatible format for placeholder '0': 'f' and 'd' are not compatible"),
        ('{0:{1}}', '{0:{2}}', "missing placeholder(s): '1'"),
        ('{} {0}', '{} {0}', 'format string mixes automatic and explicit argument numbering'),
        ('{0}', '{0', 'invalid brace format string'),
    ],
)
def test__validate_brace_format_invalid(msgid, msgstr, error):
    with pytest.raises(TranslationError, match=re.escape(error)):
        _validate_brace_format(msgid, msgstr)


@pytest.mark.parametrize(
    ('msgid', 'msgstr'),
    [
        ('{name}', '{name} {name}'),
        ('{name} {name}', '{name}'),
        ('{0} {0}', '{0} {0}'),
        ('{a[0].b!s:>{w}}', '{a[0].b!s:>{w}}'),
    ],
)
def test__validate_brace_format_valid(msgid, msgstr):
    _validate_brace_format(msgid, msgstr)
