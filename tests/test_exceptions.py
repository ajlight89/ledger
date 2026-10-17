"""Tests for the core exception hierarchy."""

import unittest

from ledger.core.exceptions import (
    CurrencyMismatchError,
    InvalidAmountError,
    InvalidCurrencyError,
    LedgerError,
)


class ExceptionHierarchyTest(unittest.TestCase):
    def test_ledger_error_is_an_exception(self) -> None:
        self.assertTrue(issubclass(LedgerError, Exception))

    def test_every_core_error_is_a_ledger_error(self) -> None:
        for error_class in (
            InvalidAmountError,
            InvalidCurrencyError,
            CurrencyMismatchError,
        ):
            with self.subTest(error_class=error_class.__name__):
                self.assertTrue(issubclass(error_class, LedgerError))

    def test_one_except_clause_catches_any_core_error(self) -> None:
        with self.assertRaises(LedgerError):
            raise InvalidAmountError("not a number")

    def test_currency_mismatch_message_and_attributes(self) -> None:
        err = CurrencyMismatchError("USD", "EUR")
        self.assertEqual(str(err), "Cannot combine USD with EUR")
        self.assertEqual((err.left, err.right), ("USD", "EUR"))