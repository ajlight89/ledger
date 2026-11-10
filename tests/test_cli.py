"""Tests for the text menu, with typed answers supplied by the test."""

import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from ledger import cli
from ledger.core.accounts import CheckingAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.money import Money

OPENED = date(2026, 10, 1)


def run(func, answers, *args):
    """Call func(*args) as if the user typed answers; return (result, printed)."""
    printed = io.StringIO()
    with patch("builtins.input", side_effect=answers), redirect_stdout(printed):
        result = func(*args)
    return result, printed.getvalue()


class TestInputHelpers(unittest.TestCase):
    """Each helper asks again until the answer can be used."""

    def test_ask_money_asks_again_and_accepts_dollar_signs_and_commas(self) -> None:
        amount, printed = run(cli.ask_money, ["abc", "$1,200"], "Amount: ")
        self.assertEqual(amount, Money(1200))
        self.assertIn("not a valid amount", printed)

    def test_ask_date_asks_again_and_blank_means_today(self) -> None:
        day, printed = run(cli.ask_date, ["13/45/2026", ""], "Date: ")
        self.assertEqual(day, date.today())
        self.assertIn("is not a date", printed)


class TestMenuActions(unittest.TestCase):
    """Menu actions change the book and save it; refused actions save nothing."""

    def setUp(self) -> None:
        self.book = Book()
        self.checking = self.book.add_account(CheckingAccount("Everyday", OPENED))
        self.checking.deposit(Money(100), OPENED, Category.INCOME, "Paycheck")
        # Replace save_book so no test writes to the real data file.
        patcher = patch("ledger.cli.storage.save_book")
        self.save = patcher.start()
        self.addCleanup(patcher.stop)

    def test_open_savings_asks_again_for_a_rate_over_100(self) -> None:
        _, printed = run(cli.open_account, ["2", "Rainy Day", "150", "4.5"], self.book)
        savings = self.book.accounts[1]
        self.assertEqual(savings.interest_rate, Decimal("4.5"))
        self.assertIn("from 0 to 100", printed)
        self.save.assert_called_once()

    def test_open_account_asks_for_a_new_name_when_taken(self) -> None:
        run(cli.open_account, ["1", "EVERYDAY", "n", "Bills"], self.book)
        self.assertEqual(self.book.accounts[1].name, "Bills")

    def test_deposit_records_and_saves(self) -> None:
        run(cli.deposit, ["1", "50", "11/01/2026", "1", "Gift"], self.book)
        self.assertEqual(self.checking.balance, Money(150))
        self.save.assert_called_once()

    def test_withdraw_too_much_then_give_up_records_nothing(self) -> None:
        _, printed = run(cli.withdraw, ["1", "500", "", "2", "Rent", "n"], self.book)
        self.assertEqual(self.checking.balance, Money(100))
        self.assertIn("Nothing was recorded.", printed)
        self.save.assert_not_called()

    def test_withdraw_too_much_then_a_smaller_amount(self) -> None:
        answers = ["1", "500", "", "2", "Rent", "y", "80"]
        run(cli.withdraw, answers, self.book)
        self.assertEqual(self.checking.balance, Money(20))
        self.save.assert_called_once()


class TestMain(unittest.TestCase):
    """The menu loop keeps going after a bad choice or a refused action."""

    @patch("ledger.cli.setup_logging")
    @patch("ledger.cli.storage.load_book", return_value=Book())
    def test_bad_choice_and_refused_action_return_to_the_menu(
        self, _load, _logging
    ) -> None:
        _, printed = run(cli.main, ["7", "3", "q"])
        self.assertIn("Please choose one of the numbers shown", printed)
        self.assertIn("There are no accounts yet", printed)
        self.assertIn("Goodbye.", printed)


if __name__ == "__main__":
    unittest.main()
