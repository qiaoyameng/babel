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

import decimal

import pytest

from babel import numbers


def test_can_parse_decimals():
    v = decimal.Decimal('1099.98')
    assert numbers.parse_decimal('1,099.98', locale='en_US') == v
    assert numbers.parse_decimal('1.099,98', locale='de') == v
    assert numbers.parse_decimal('1,099.98', locale='ar', numbering_system="default") == v  # fmt: skip
    assert numbers.parse_decimal('1٬099٫98', locale='ar_EG', numbering_system="default") == v  # fmt: skip
    with pytest.raises(numbers.NumberFormatError):
        numbers.parse_decimal('2,109,998', locale='de')
    with pytest.raises(numbers.UnsupportedNumberingSystemError):
        numbers.parse_decimal('2,109,998', locale='de', numbering_system="unknown")


def test_parse_decimal_strict_mode():
    # Numbers with a misplaced grouping symbol should be rejected
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_decimal('11.11', locale='de', strict=True)
    assert info.value.suggestions == ['1.111', '11,11']
    # Numbers with two misplaced grouping symbols should be rejected
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_decimal('80.00.00', locale='de', strict=True)
    assert info.value.suggestions == ['800.000']
    # Partially grouped numbers should be rejected
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_decimal('2000,000', locale='en_US', strict=True)
    assert info.value.suggestions == ['2,000,000', '2,000']
    # Numbers with duplicate grouping symbols should be rejected
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_decimal('0,,000', locale='en_US', strict=True)
    assert info.value.suggestions == ['0']
    # Return only suggestion for 0 on strict
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_decimal('0.00', locale='de', strict=True)
    assert info.value.suggestions == ['0']
    # Properly formatted numbers should be accepted
    assert str(numbers.parse_decimal('1.001', locale='de', strict=True)) == '1001'
    # Trailing zeroes should be accepted
    assert str(numbers.parse_decimal('3.00', locale='en_US', strict=True)) == '3.00'
    # Numbers with a grouping symbol and no trailing zeroes should be accepted
    assert str(numbers.parse_decimal('3,400.6', locale='en_US', strict=True)) == '3400.6'
    # Numbers with a grouping symbol and trailing zeroes (not all zeroes after decimal) should be accepted
    assert str(numbers.parse_decimal('3,400.60', locale='en_US', strict=True)) == '3400.60'
    # Numbers with a grouping symbol and trailing zeroes (all zeroes after decimal) should be accepted
    assert str(numbers.parse_decimal('3,400.00', locale='en_US', strict=True)) == '3400.00'
    assert str(numbers.parse_decimal('3,400.0000', locale='en_US', strict=True)) == '3400.0000'
    # Numbers with a grouping symbol and no decimal part should be accepted
    assert str(numbers.parse_decimal('3,800', locale='en_US', strict=True)) == '3800'
    # Numbers without any grouping symbol should be accepted
    assert str(numbers.parse_decimal('2000.1', locale='en_US', strict=True)) == '2000.1'
    # Numbers without any grouping symbol and no decimal should be accepted
    assert str(numbers.parse_decimal('2580', locale='en_US', strict=True)) == '2580'
    # High precision numbers should be accepted
    assert str(numbers.parse_decimal('5,000001', locale='fr', strict=True)) == '5.000001'


def test_parse_currency_us_format():
    amount, currency = numbers.parse_currency(
        '$1,234.50', locale='en_US', allowed_currencies={'USD'},
    )
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'USD'
    # Currency codes are recognized as well as symbols
    amount, currency = numbers.parse_currency('USD 1,234.50', locale='en_US')
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'USD'


def test_parse_currency_german_format():
    amount, currency = numbers.parse_currency('1.234,50 €', locale='de_DE')
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'EUR'
    amount, currency = numbers.parse_currency('1.234,50 EUR', locale='de_DE')
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'EUR'


def test_parse_currency_french_format():
    amount, currency = numbers.parse_currency('1 234,50 €', locale='fr_FR')
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'EUR'


def test_parse_currency_negative():
    amount, currency = numbers.parse_currency(
        '-$1,234.50', locale='en_US', allowed_currencies={'USD'},
    )
    assert amount == decimal.Decimal('-1234.50')
    assert currency == 'USD'
    amount, currency = numbers.parse_currency('-1.234,50 €', locale='de_DE')
    assert amount == decimal.Decimal('-1234.50')
    assert currency == 'EUR'


def test_parse_currency_accounting_parentheses():
    amount, currency = numbers.parse_currency(
        '($1,234.50)', locale='en_US', allowed_currencies={'USD'},
    )
    assert amount == decimal.Decimal('-1234.50')
    assert currency == 'USD'
    amount, currency = numbers.parse_currency('(1.234,50 €)', locale='de_DE')
    assert amount == decimal.Decimal('-1234.50')
    assert currency == 'EUR'


def test_parse_currency_without_marker():
    amount, currency = numbers.parse_currency('1,234.50', locale='en_US')
    assert amount == decimal.Decimal('1234.50')
    assert currency is None
    amount, currency = numbers.parse_currency('1.234,50', locale='de_DE')
    assert amount == decimal.Decimal('1234.50')
    assert currency is None


def test_parse_currency_ambiguous_symbol():
    # "$" is used by many currencies and must not be resolved arbitrarily
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_currency('$1,234.50', locale='en_US')
    assert 'USD' in info.value.suggestions
    assert 'CAD' in info.value.suggestions
    # An allowed set that still contains multiple candidates stays ambiguous
    with pytest.raises(numbers.NumberFormatError) as info:
        numbers.parse_currency(
            '$1,234.50', locale='en_US', allowed_currencies={'USD', 'CAD'},
        )
    assert info.value.suggestions == ['CAD', 'USD']
    # An allowed set with a single matching candidate disambiguates
    amount, currency = numbers.parse_currency(
        '$1,234.50', locale='en_US', allowed_currencies={'USD', 'EUR'},
    )
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'USD'


def test_parse_currency_disallowed_currency():
    with pytest.raises(numbers.NumberFormatError):
        numbers.parse_currency(
            '1.234,50 €', locale='de_DE', allowed_currencies={'USD'},
        )
    with pytest.raises(numbers.UnknownCurrencyError):
        numbers.parse_currency(
            '1.234,50 €', locale='de_DE', allowed_currencies={'NOPE'},
        )


def test_parse_currency_strict():
    # Properly formatted amounts are accepted
    amount, currency = numbers.parse_currency('1.234,50 €', locale='de_DE', strict=True)
    assert amount == decimal.Decimal('1234.50')
    assert currency == 'EUR'
    # Misplaced grouping symbols are rejected
    with pytest.raises(numbers.NumberFormatError):
        numbers.parse_currency('11.11 €', locale='de_DE', strict=True)
    # Repeated currency symbols are rejected
    with pytest.raises(numbers.NumberFormatError):
        numbers.parse_currency(
            '$$1,234.50', locale='en_US', allowed_currencies={'USD'}, strict=True,
        )
