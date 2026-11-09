"""Tests for the Book facade and saving it to a file."""

import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from ledger.core.accounts import CheckingAccount, CreditCardAccount, SavingsAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import DuplicateAccountError, InsufficientFundsError
from ledger.core.money import Money
from ledger.core.storage import load_book, save_book

OPENED = date(2026, 10, 1)


class TestBook(unittest.TestCase):
    """Book holds the accounts and moves money between them."""

    def setUp(self) -> None:
        self.book = Book()
        self.checking = self.book.add_account(CheckingAccount("Checking", OPENED))
        self.savings = self.book.add_account(SavingsAccount("Savings", OPENED))
        self.checking.deposit(Money(100), OPENED, Category.INCOME, "Paycheck")

    def test_a_duplicate_name_is_refused_ignoring_case(self) -> None:
        with self.assertRaises(DuplicateAccountError):
            self.book.add_account(CheckingAccount("CHECKING", OPENED))
        self.assertEqual(len(self.book.accounts), 2)

    def test_a_transfer_moves_the_money(self) -> None:
        self.book.transfer(
            Money(40), self.checking.id, self.savings.id, OPENED, "To savings"
        )
        self.assertEqual(self.checking.balance, Money(60))
        self.assertEqual(self.savings.balance, Money(40))

    def test_a_refused_transfer_changes_neither_account(self) -> None:
        with self.assertRaises(InsufficientFundsError):
            self.book.transfer(
                Money(500), self.checking.id, self.savings.id, OPENED, "Too much"
            )
        self.assertEqual(len(self.checking.transactions), 1)
        self.assertEqual(len(self.savings.transactions), 0)


class TestSaveAndLoad(unittest.TestCase):
    """A book saved to a file loads back the same."""

    def test_a_round_trip_keeps_every_account_and_balance(self) -> None:
        book = Book()
        checking = book.add_account(
            CheckingAccount("Checking", OPENED, overdraft_enabled=True)
        )
        book.add_account(
            SavingsAccount("Savings", OPENED, interest_rate=Decimal("4.5"))
        )
        card = book.add_account(
            CreditCardAccount("Visa", OPENED, credit_limit=Money(2000))
        )
        checking.deposit(Money(250), OPENED, Category.INCOME, "Paycheck")
        card.withdraw(Money(75), OPENED, Category.DINING_OUT, "Dinner")

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "ledger.json"
            save_book(book, path)
            loaded = load_book(path)

        self.assertEqual(
            [(a.name, type(a), a.balance) for a in loaded.accounts],
            [(a.name, type(a), a.balance) for a in book.accounts],
        )
