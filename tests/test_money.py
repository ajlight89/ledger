"""Tests for the Money value class."""

import unittest
from decimal import Decimal

from ledger.core.exceptions import CurrencyMismatchError, InvalidAmountError
from ledger.core.money import Money


class TestMoney(unittest.TestCase):
    """Money keeps exact amounts and never mixes currencies."""

    def test_add_and_subtract(self) -> None:
        a = Money.from_str("10.25")
        b = Money.from_str("2.50")
        self.assertEqual(a + b, Money.from_str("12.75"))
        self.assertEqual(a - b, Money.from_str("7.75"))

    def test_mixing_currencies_raises(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            Money(5) + Money(5, "EUR")

    def test_str_shows_dollars_with_commas(self) -> None:
        self.assertEqual(str(Money(Decimal("1234.56"))), "$1,234.56")
        self.assertEqual(str(Money(Decimal("-54.2"))), "-$54.20")

    def test_from_str_refuses_text_that_is_not_a_number(self) -> None:
        with self.assertRaises(InvalidAmountError):
            Money.from_str("abc")


if __name__ == "__main__":
    unittest.main()
