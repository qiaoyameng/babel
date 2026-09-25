# Copyright (C) 2026 the Babel team
# All rights reserved.
#
# This software is licensed as described in the file LICENSE, which
# you should have received as part of this distribution. The terms
# are also available at https://github.com/python-babel/babel/commits/master/.

import datetime
from io import BytesIO

from babel.messages import merge
from babel.messages.catalog import Catalog, Message
from babel.messages.pofile import read_po, write_po
from babel.util import UTC

CREATED = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def make_catalog(messages=(), obsolete=(), **kwargs):
    kwargs.setdefault('locale', 'de')
    kwargs.setdefault('creation_date', CREATED)
    catalog = Catalog(**kwargs)
    for message in messages:
        catalog[message.id] = message
    for message in obsolete:
        catalog.obsolete[catalog._key_for(message.id, message.context)] = message
    return catalog


def merge_three(base_messages, ours_messages, theirs_messages, **kwargs):
    base = make_catalog(base_messages, **kwargs)
    ours = make_catalog(ours_messages, **kwargs)
    theirs = make_catalog(theirs_messages, **kwargs)
    return merge.merge_catalogs(base, ours, theirs)


def test_translation_and_comments_merge_automatically():
    result = merge_three(
        [Message('Hello', 'Hallo', locations=[('app.py', 1)])],
        [Message('Hello', 'Servus', locations=[('app.py', 1)])],
        [Message('Hello', 'Hallo', locations=[('app.py', 2)],
                 user_comments=['reviewed'])],
    )
    assert result.ok
    message = result.catalog['Hello']
    assert message.string == 'Servus'
    assert message.locations == [('app.py', 2)]
    assert message.user_comments == ['reviewed']
    assert not message.fuzzy
    assert [m.id for m in result.auto_merged] == ['Hello']


def test_translation_conflict_keeps_base_and_marks_fuzzy():
    result = merge_three(
        [Message('Hello', 'Hallo')],
        [Message('Hello', 'Servus')],
        [Message('Hello', 'Moin')],
    )
    assert result.has_conflicts
    conflict, = result.conflicts
    assert conflict.kind == merge.TRANSLATION_CONFLICT
    assert conflict.base == 'Hallo'
    assert conflict.ours == 'Servus'
    assert conflict.theirs == 'Moin'
    message = result.catalog['Hello']
    # Neither side is treated as the final translation.
    assert message.string == 'Hallo'
    assert message.fuzzy
    assert conflict.message is message
    assert result.conflicts_for('Hello') == [conflict]


def test_identical_changes_on_both_sides_merge_cleanly():
    result = merge_three(
        [Message('Hello', 'Hallo')],
        [Message('Hello', 'Servus')],
        [Message('Hello', 'Servus')],
    )
    assert result.ok
    assert result.catalog['Hello'].string == 'Servus'
    assert result.auto_merged == []


def test_context_distinguishes_messages():
    result = merge_three(
        [Message('Open', 'Öffnen', context='menu'),
         Message('Open', 'Offen', context='adjective')],
        [Message('Open', 'Aufmachen', context='menu'),
         Message('Open', 'Offen', context='adjective')],
        [Message('Open', 'Öffnen', context='menu'),
         Message('Open', 'Geöffnet', context='adjective')],
    )
    assert result.ok
    assert result.catalog.get('Open', context='menu').string == 'Aufmachen'
    assert result.catalog.get('Open', context='adjective').string == 'Geöffnet'


def test_added_messages_from_both_sides_are_kept():
    result = merge_three(
        [Message('Hello', 'Hallo')],
        [Message('Hello', 'Hallo'), Message('New A', 'Neu A')],
        [Message('Hello', 'Hallo'), Message('New B', 'Neu B')],
    )
    assert result.ok
    assert result.catalog['New A'].string == 'Neu A'
    assert result.catalog['New B'].string == 'Neu B'
    # Ancestor order first, then additions in deterministic order.
    assert [m.id for m in result.catalog] == ['', 'Hello', 'New A', 'New B']


def test_plural_length_change_on_one_side_merges():
    result = merge_three(
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        locale='de',
    )
    assert result.ok
    assert result.catalog['apple'].string == ('Apfel', 'Äpfel', 'Äpfel')


def test_plural_length_change_with_translation_change_on_other_side():
    result = merge_three(
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Apfeln'))],
    )
    assert result.ok
    assert result.catalog['apple'].string == ('Apfel', 'Apfeln', 'Äpfel')


def test_plural_length_conflict():
    result = merge_three(
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Zwei', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Drei', 'Viele', 'Ganz viele'))],
    )
    assert result.has_conflicts
    conflict, = result.conflicts
    assert conflict.kind == merge.PLURAL_LENGTH_CONFLICT
    message = result.catalog['apple']
    assert message.string == ('Apfel', 'Äpfel')
    assert message.fuzzy


def test_plural_content_conflict_same_length():
    result = merge_three(
        [Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        [Message(('apple', 'apples'), ('Apfel', 'Birnen'))],
        [Message(('apple', 'apples'), ('Apfel', 'Nüsse'))],
    )
    conflict, = result.conflicts
    assert conflict.kind == merge.TRANSLATION_CONFLICT
    assert result.catalog['apple'].string == ('Apfel', 'Äpfel')


def test_delete_vs_unchanged_deletes():
    result = merge_three(
        [Message('Old', 'Alt'), Message('Keep', 'Behalten')],
        [Message('Keep', 'Behalten')],
        [Message('Old', 'Alt'), Message('Keep', 'Behalten')],
    )
    assert result.ok
    assert 'Old' not in result.catalog
    assert 'Keep' in result.catalog


def test_delete_vs_modify_conflicts():
    result = merge_three(
        [Message('Old', 'Alt')],
        [],
        [Message('Old', 'Uralt')],
    )
    assert result.has_conflicts
    conflict, = result.conflicts
    assert conflict.kind == merge.DELETE_VS_MODIFY_CONFLICT
    assert conflict.ours is None
    assert conflict.theirs.string == 'Uralt'
    message = result.catalog['Old']
    assert message.string == 'Uralt'
    assert message.fuzzy


def test_delete_on_both_sides_deletes():
    result = merge_three([Message('Old', 'Alt')], [], [])
    assert result.ok
    assert 'Old' not in result.catalog


def test_obsolete_revival_on_one_side():
    result = merge_three(
        [],
        [Message('Zombie', 'Untot')],
        [],
        obsolete=[Message('Zombie', 'Alt')],
    )
    assert result.ok
    assert result.catalog['Zombie'].string == 'Untot'
    assert 'Zombie' not in result.catalog.obsolete


def test_obsolete_revival_conflict():
    base = make_catalog(obsolete=[Message('Zombie', 'Alt')])
    ours = make_catalog([Message('Zombie', 'Untot')])
    theirs = make_catalog([Message('Zombie', 'Wiederbelebt')])
    result = merge.merge_catalogs(base, ours, theirs)
    assert result.has_conflicts
    conflict, = result.conflicts
    assert conflict.kind == merge.TRANSLATION_CONFLICT
    message = result.catalog['Zombie']
    assert message.string == 'Alt'
    assert message.fuzzy


def test_obsolete_vs_modify_conflicts():
    base = make_catalog([Message('Old', 'Alt')])
    ours = make_catalog(obsolete=[Message('Old', 'Alt')])
    theirs = make_catalog([Message('Old', 'Uralt')])
    result = merge.merge_catalogs(base, ours, theirs)
    assert result.has_conflicts
    conflict, = result.conflicts
    assert conflict.kind == merge.OBSOLETE_VS_MODIFY_CONFLICT
    message = result.catalog['Old']
    assert message.string == 'Uralt'
    assert message.fuzzy


def test_obsoleting_on_one_side_only():
    base = make_catalog([Message('Old', 'Alt')])
    ours = make_catalog(obsolete=[Message('Old', 'Alt')])
    theirs = make_catalog([Message('Old', 'Alt')])
    result = merge.merge_catalogs(base, ours, theirs)
    assert result.ok
    assert 'Old' not in result.catalog
    assert 'Old' in result.catalog.obsolete


def test_header_fields_merge_independently():
    base = make_catalog(last_translator='Alice <a@example.com>',
                        language_team='de <de@example.com>')
    ours = make_catalog(last_translator='Bob <b@example.com>',
                        language_team='de <de@example.com>')
    theirs = make_catalog(last_translator='Alice <a@example.com>',
                          language_team='German <german@example.com>')
    result = merge.merge_catalogs(base, ours, theirs)
    assert result.ok
    assert result.catalog.last_translator == 'Bob <b@example.com>'
    assert result.catalog.language_team == 'German <german@example.com>'


def test_header_conflict_is_structured():
    base = make_catalog(last_translator='Alice <a@example.com>')
    ours = make_catalog(last_translator='Bob <b@example.com>')
    theirs = make_catalog(last_translator='Carol <c@example.com>')
    result = merge.merge_catalogs(base, ours, theirs)
    assert result.has_conflicts
    conflict, = result.conflicts
    assert conflict.kind == merge.HEADER_CONFLICT
    assert conflict.id is None
    assert conflict.detail == 'last_translator'
    assert conflict.ours == 'Bob <b@example.com>'
    assert conflict.theirs == 'Carol <c@example.com>'
    # The ancestor value is kept, no side wins.
    assert result.catalog.last_translator == 'Alice <a@example.com>'


def test_header_dates_take_latest_without_conflict():
    earlier = datetime.datetime(2026, 2, 1, tzinfo=UTC)
    later = datetime.datetime(2026, 3, 1, tzinfo=UTC)
    base = make_catalog(revision_date=CREATED)
    ours = make_catalog(revision_date=earlier)
    theirs = make_catalog(revision_date=later)
    result = merge.merge_catalogs(base, ours, theirs)
    assert result.ok
    assert result.catalog.revision_date == later


def test_flags_merge_as_union():
    result = merge_three(
        [Message('Hello', 'Hallo')],
        [Message('Hello', 'Hallo', flags=['fuzzy'])],
        [Message('Hello', 'Hallo', flags=['custom-flag'])],
    )
    assert result.ok
    assert result.catalog['Hello'].flags == {'fuzzy', 'custom-flag'}


def test_locations_union_when_both_sides_change():
    result = merge_three(
        [Message('Hello', 'Hallo', locations=[('app.py', 1)])],
        [Message('Hello', 'Hallo', locations=[('app.py', 1), ('a.py', 2)])],
        [Message('Hello', 'Hallo', locations=[('app.py', 1), ('b.py', 3)])],
    )
    assert result.ok
    assert result.catalog['Hello'].locations == [
        ('app.py', 1), ('a.py', 2), ('b.py', 3),
    ]


def catalog_snapshot(catalog):
    return {
        'headers': list(catalog.mime_headers),
        'fuzzy': catalog.fuzzy,
        'messages': [
            (m.id, m.context, m.string, m.locations, sorted(m.flags),
             m.auto_comments, m.user_comments, m.previous_id)
            for m in catalog
        ],
        'obsolete': [
            (m.id, m.context, m.string)
            for m in catalog.obsolete.values()
        ],
    }


def test_clean_merge_roundtrips_through_po():
    result = merge_three(
        [Message('Hello', 'Hallo', locations=[('app.py', 1)]),
         Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        [Message('Hello', 'Servus', locations=[('app.py', 1)]),
         Message(('apple', 'apples'), ('Apfel', 'Äpfel'))],
        [Message('Hello', 'Hallo', locations=[('app.py', 2)],
                 user_comments=['reviewed']),
         Message(('apple', 'apples'), ('Apfel', 'Apfeln'))],
    )
    assert result.ok
    buffer = BytesIO()
    write_po(buffer, result.catalog)
    buffer.seek(0)
    reread = read_po(buffer)
    assert catalog_snapshot(reread) == catalog_snapshot(result.catalog)


def test_conflicted_merge_does_not_emit_either_translation():
    result = merge_three(
        [Message('Hello', 'Hallo')],
        [Message('Hello', 'Servus')],
        [Message('Hello', 'Moin')],
    )
    buffer = BytesIO()
    write_po(buffer, result.catalog)
    output = buffer.getvalue().decode('utf-8')
    assert 'Servus' not in output
    assert 'Moin' not in output
    assert 'Hallo' in output
    assert 'fuzzy' in output
