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

from __future__ import annotations

import datetime
from io import BytesIO

import pytest

from babel.messages import pofile
from babel.messages.catalog import Catalog
from babel.messages.merge import MergeConflict, merge_catalogs
from babel.util import LOCALTZ

CREATED = datetime.datetime(2025, 1, 1, 12, 0, tzinfo=LOCALTZ)
REVISED = datetime.datetime(2025, 2, 1, 12, 0, tzinfo=LOCALTZ)


def make_catalog(**kwargs) -> Catalog:
    kwargs.setdefault('locale', 'de')
    kwargs.setdefault('creation_date', CREATED)
    kwargs.setdefault('revision_date', REVISED)
    kwargs.setdefault('fuzzy', False)
    return Catalog(**kwargs)


def test_auto_merge_translation_and_metadata():
    base = make_catalog()
    base.add('hello', 'Hallo', locations=[('main.py', 1)])

    ours = make_catalog()
    ours.add('hello', 'Hallo Welt', locations=[('main.py', 1)])

    theirs = make_catalog()
    theirs.add('hello', 'Hallo', locations=[('main.py', 1), ('util.py', 7)],
               user_comments=['greeting'])

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    message = merged.get('hello')
    assert message.string == 'Hallo Welt'  # from ours
    assert message.locations == [('main.py', 1), ('util.py', 7)]  # from theirs
    assert message.user_comments == ['greeting']  # from theirs
    assert not message.fuzzy


def test_merge_aligns_by_context():
    base = make_catalog()
    base.add('open', 'offen', context='menu')
    base.add('open', 'oeffnen', context='verb')

    ours = make_catalog()
    ours.add('open', 'geoeffnet', context='menu')
    ours.add('open', 'oeffnen', context='verb')

    theirs = make_catalog()
    theirs.add('open', 'offen', context='menu')
    theirs.add('open', 'aufmachen', context='verb')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert merged.get('open', context='menu').string == 'geoeffnet'
    assert merged.get('open', context='verb').string == 'aufmachen'


def test_translation_conflict_keeps_base_and_flags_fuzzy():
    base = make_catalog()
    base.add('hello', 'Hallo')
    ours = make_catalog()
    ours.add('hello', 'Hallo Welt')
    theirs = make_catalog()
    theirs.add('hello', 'Guten Tag')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.kind == 'translation'
    assert conflict.id == 'hello'
    assert conflict.ours.string == 'Hallo Welt'
    assert conflict.theirs.string == 'Guten Tag'

    message = merged.get('hello')
    # Neither side's translation is used as the final result.
    assert message.string == 'Hallo'
    assert message.fuzzy


def test_add_add_conflict_has_empty_translation():
    base = make_catalog()
    ours = make_catalog()
    ours.add('new', 'Neu A')
    theirs = make_catalog()
    theirs.add('new', 'Neu B')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert [c.kind for c in conflicts] == ['translation']
    message = merged.get('new')
    assert message.string == ''
    assert message.fuzzy


def test_identical_additions_merge_cleanly():
    base = make_catalog()
    ours = make_catalog()
    ours.add('new', 'Neu', locations=[('a.py', 1)])
    theirs = make_catalog()
    theirs.add('new', 'Neu', locations=[('a.py', 1)])

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert merged.get('new').string == 'Neu'


def test_plural_length_change_conflict():
    base = make_catalog()
    base.add(('apple', 'apples'), ('Apfel', 'Aepfel'))

    ours = make_catalog()
    ours.add(('apple', 'apples'), ('Apfel', 'Aepfel', 'Aepfel viele'))

    theirs = make_catalog()
    theirs.add(('apple', 'apples'), ('Apfel!', 'Aepfel!'))

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert [c.kind for c in conflicts] == ['plural-length']
    message = merged.get('apple')
    assert message.string == ('Apfel', 'Aepfel')
    assert message.fuzzy


def test_plural_translation_auto_merge():
    base = make_catalog()
    base.add(('apple', 'apples'), ('Apfel', 'Aepfel'))
    ours = make_catalog()
    ours.add(('apple', 'apples'), ('Apfel', 'Aepfel', 'Aepfel viele'))
    theirs = make_catalog()
    theirs.add(('apple', 'apples'), ('Apfel', 'Aepfel'),
               user_comments=['fruit'])

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    message = merged.get('apple')
    assert message.string == ('Apfel', 'Aepfel', 'Aepfel viele')
    assert message.user_comments == ['fruit']


def test_delete_vs_modify_conflict():
    base = make_catalog()
    base.add('old', 'Alt')
    ours = make_catalog()  # deletes the message
    theirs = make_catalog()
    theirs.add('old', 'Alt aber neu')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert [c.kind for c in conflicts] == ['delete-vs-modify']
    assert conflicts[0].ours is None
    # The modified message is kept (no data loss) but flagged for review.
    message = merged.get('old')
    assert message.string == 'Alt aber neu'
    assert message.fuzzy


def test_clean_delete_and_clean_modify_merge():
    base = make_catalog()
    base.add('gone', 'Weg')
    base.add('kept', 'Behalten')

    ours = make_catalog()  # deletes 'gone', keeps 'kept'
    ours.add('kept', 'Behalten')

    theirs = make_catalog()  # modifies 'kept', leaves 'gone' alone
    theirs.add('gone', 'Weg')
    theirs.add('kept', 'Aufbewahrt')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert 'gone' not in merged
    assert merged.get('kept').string == 'Aufbewahrt'


def test_obsolete_resurrection():
    base = make_catalog()
    base.obsolete['zombie'] = base.add('zombie', 'Zombie')
    base._messages.clear()

    ours = make_catalog()  # resurrects the message with a new translation
    ours.add('zombie', 'Wiederbelebt')

    theirs = make_catalog()  # leaves it obsolete
    theirs.obsolete['zombie'] = theirs.add('zombie', 'Zombie')
    theirs._messages.clear()

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert 'zombie' in merged
    assert 'zombie' not in merged.obsolete
    assert merged.get('zombie').string == 'Wiederbelebt'


def test_conflicting_resurrections_conflict():
    base = make_catalog()
    base.obsolete['zombie'] = base.add('zombie', 'Zombie')
    base._messages.clear()

    ours = make_catalog()
    ours.add('zombie', 'A')
    theirs = make_catalog()
    theirs.add('zombie', 'B')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert [c.kind for c in conflicts] == ['translation']
    message = merged.get('zombie')
    assert message.string == 'Zombie'
    assert message.fuzzy


def test_header_metadata_merged_field_by_field():
    base = make_catalog(last_translator='Alice <a@example.com>',
                        language_team='de <de@example.com>')
    ours = make_catalog(last_translator='Bob <b@example.com>',
                        language_team='de <de@example.com>')
    theirs = make_catalog(last_translator='Alice <a@example.com>',
                          language_team='German <german@example.com>')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert merged.last_translator == 'Bob <b@example.com>'
    assert merged.language_team == 'German <german@example.com>'


def test_header_conflict_keeps_base_value():
    base = make_catalog(last_translator='Alice <a@example.com>')
    ours = make_catalog(last_translator='Bob <b@example.com>')
    theirs = make_catalog(last_translator='Carol <c@example.com>')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert [c.kind for c in conflicts] == ['header']
    assert conflicts[0].field == 'last_translator'
    assert conflicts[0].ours == 'Bob <b@example.com>'
    assert conflicts[0].theirs == 'Carol <c@example.com>'
    assert merged.last_translator == 'Alice <a@example.com>'


def test_revision_date_takes_latest():
    earlier = datetime.datetime(2025, 3, 1, 12, 0, tzinfo=LOCALTZ)
    later = datetime.datetime(2025, 4, 1, 12, 0, tzinfo=LOCALTZ)
    base = make_catalog()
    ours = make_catalog(revision_date=earlier)
    theirs = make_catalog(revision_date=later)

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert merged.revision_date == later


def test_plural_forms_header_conflict():
    base = make_catalog()
    ours = make_catalog()
    theirs = make_catalog()
    base._num_plurals, base._plural_expr = 2, '(n != 1)'
    ours._num_plurals, ours._plural_expr = 3, '(n % 10 == 1)'
    theirs._num_plurals, theirs._plural_expr = 4, '(n % 100 == 1)'

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert [c.kind for c in conflicts] == ['header']
    assert conflicts[0].field == 'Plural-Forms'
    assert merged.num_plurals == 2


def test_merge_is_per_message_not_per_file():
    base = make_catalog()
    base.add('a', 'A')
    base.add('b', 'B')

    ours = make_catalog()
    ours.add('a', 'A2')
    ours.add('b', 'B')

    theirs = make_catalog()
    theirs.add('a', 'A')
    theirs.add('b', 'B2')

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert merged.get('a').string == 'A2'
    assert merged.get('b').string == 'B2'


def _write(catalog: Catalog) -> bytes:
    buf = BytesIO()
    pofile.write_po(buf, catalog, omit_header=False)
    return buf.getvalue()


def test_conflict_free_output_is_stable_when_reread():
    base = make_catalog()
    base.add('hello', 'Hallo', locations=[('main.py', 1)])
    base.add(('apple', 'apples'), ('Apfel', 'Aepfel'))
    base.obsolete['old'] = base.get('hello').clone()
    base.obsolete['old'].id = 'old'
    base.obsolete['old'].string = 'Alt'

    ours = make_catalog()
    ours.add('hello', 'Hallo Welt', locations=[('main.py', 1)])
    ours.add(('apple', 'apples'), ('Apfel', 'Aepfel'))
    ours.obsolete['old'] = base.obsolete['old'].clone()

    theirs = make_catalog()
    theirs.add('hello', 'Hallo', locations=[('main.py', 1), ('util.py', 3)])
    theirs.add(('apple', 'apples'), ('Apfel', 'Aepfel2'))
    theirs.obsolete['old'] = base.obsolete['old'].clone()

    merged, conflicts = merge_catalogs(base, ours, theirs)
    assert conflicts == []

    first = _write(merged)
    reread = pofile.read_po(BytesIO(first), locale='de')
    second = _write(reread)
    assert first == second

    # Content survives the round trip.
    assert reread.get('hello').string == 'Hallo Welt'
    assert reread.get('hello').locations == [('main.py', 1), ('util.py', 3)]
    assert reread.get('apple').string == ('Apfel', 'Aepfel2')
    assert 'old' in reread.obsolete


def test_conflicted_output_remains_parseable():
    base = make_catalog()
    base.add('hello', 'Hallo')
    ours = make_catalog()
    ours.add('hello', 'Hallo Welt')
    theirs = make_catalog()
    theirs.add('hello', 'Guten Tag')

    merged, conflicts = merge_catalogs(base, ours, theirs)
    assert len(conflicts) == 1

    reread = pofile.read_po(BytesIO(_write(merged)), locale='de')
    message = reread.get('hello')
    assert message.string == 'Hallo'
    assert message.fuzzy


def test_conflict_str():
    conflict = MergeConflict(kind='translation', id='hello',
                             description='both sides changed the translation differently')
    assert "msgid 'hello'" in str(conflict)
    header_conflict = MergeConflict(kind='header', field='last_translator')
    assert 'last_translator' in str(header_conflict)


def test_both_sides_made_obsolete_differently():
    base = make_catalog()
    base.add('gone', 'Weg')

    ours = make_catalog()
    ours.obsolete['gone'] = ours.add('gone', 'Weg', user_comments=['ours note'])
    ours._messages.clear()

    theirs = make_catalog()
    theirs.obsolete['gone'] = theirs.add('gone', 'Weg', user_comments=['theirs note'])
    theirs._messages.clear()

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert 'gone' not in merged
    assert 'gone' in merged.obsolete
    assert merged.obsolete['gone'].user_comments == ['ours note', 'theirs note']


def test_obsolete_vs_purge_keeps_obsolete():
    base = make_catalog()
    base.obsolete['old'] = base.add('old', 'Alt')
    base._messages.clear()

    ours = make_catalog()  # purges the obsolete message entirely
    theirs = make_catalog()
    theirs.obsolete['old'] = theirs.add('old', 'Alt', user_comments=['keep me'])
    theirs._messages.clear()

    merged, conflicts = merge_catalogs(base, ours, theirs)

    assert conflicts == []
    assert merged.obsolete['old'].user_comments == ['keep me']


def test_merge_is_deterministic():
    def build():
        base = make_catalog()
        base.add('a', 'A')
        base.add('b', 'B')
        ours = make_catalog()
        ours.add('a', 'A1')
        ours.add('b', 'B')
        ours.add('c', 'C1')
        theirs = make_catalog()
        theirs.add('a', 'A')
        theirs.add('b', 'B2')
        theirs.add('d', 'D2')
        return base, ours, theirs

    merged_1, conflicts_1 = merge_catalogs(*build())
    merged_2, conflicts_2 = merge_catalogs(*build())

    assert conflicts_1 == conflicts_2 == []
    assert _write(merged_1) == _write(merged_2)
    assert [m.id for m in merged_1 if m.id] == ['a', 'b', 'c', 'd']
