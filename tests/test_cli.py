"""Tests for the text menu, with typed answers supplied by the test."""

import io
import unittest
from contextlib import redirect_stdout
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from ledger import cli
from ledger.core import importer
from ledger.core.accounts import CheckingAccount, CreditCardAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import CsvFormatError
from ledger.core.money import Money

OPENED = date(2026, 10, 1)
SAMPLE = Path(__file__).parent.parent / "sample.csv"


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


class TestTransferRenameImport(unittest.TestCase):
    """Transfers, renaming and CSV import from the menu."""

    def setUp(self) -> None:
        self.book = Book()
        self.checking = self.book.add_account(CheckingAccount("Everyday", OPENED))
        self.card = self.book.add_account(
            CreditCardAccount("Visa", OPENED, credit_limit=Money(500))
        )
        self.checking.deposit(Money(100), OPENED, Category.INCOME, "Paycheck")
        patcher = patch("ledger.cli.storage.save_book")
        self.save = patcher.start()
        self.addCleanup(patcher.stop)

    def test_transfer_pays_the_card_and_saves(self) -> None:
        run(cli.transfer, ["1", "2", "40", "", "Card payment"], self.book)
        self.assertEqual(self.checking.balance, Money(60))
        self.assertEqual(self.card.balance, Money(40))
        self.save.assert_called_once()

    def test_transfer_too_much_then_give_up_changes_nothing(self) -> None:
        answers = ["1", "2", "500", "", "Card payment", "n"]
        _, printed = run(cli.transfer, answers, self.book)
        self.assertEqual(self.checking.balance, Money(100))
        self.assertEqual(self.card.balance, Money(0))
        self.assertIn("Nothing was recorded.", printed)
        self.save.assert_not_called()

    def test_rename_asks_again_when_the_name_is_taken(self) -> None:
        _, printed = run(cli.rename_account, ["1", "visa", "Bills"], self.book)
        self.assertEqual(self.checking.name, "Bills")
        self.assertIn("already exists", printed)

    def test_import_adds_the_sample_rows_and_saves(self) -> None:
        run(cli.import_transactions, ["1", f'"{SAMPLE}"'], self.book)
        self.assertEqual(len(self.checking.transactions), 16)
        self.save.assert_called_once()

    def test_import_of_a_missing_file_is_refused(self) -> None:
        with self.assertRaises(CsvFormatError):
            run(cli.import_transactions, ["1", "no_such_file.csv"], self.book)
        self.save.assert_not_called()


class TestReports(unittest.TestCase):
    """The statement and spending reports print the sample month correctly."""

    def setUp(self) -> None:
        self.book = Book()
        checking = self.book.add_account(CheckingAccount("Everyday", OPENED))
        importer.import_csv(checking, SAMPLE)

    def test_ask_month_asks_again_and_blank_means_this_month(self) -> None:
        (year, month), printed = run(cli.ask_month, ["13/2026", ""], "Month: ")
        self.assertEqual((year, month), (date.today().year, date.today().month))
        self.assertIn("is not a month", printed)

    def test_statement_shows_rows_and_the_closing_balance(self) -> None:
        _, printed = run(cli.show_statement, ["1", "10/2026"], self.book)
        self.assertIn("Opening balance: $0.00", printed)
        self.assertIn("MAPLE APTS RENT", printed)
        self.assertIn("Closing balance: $1,460.65", printed)

    def test_statement_for_an_empty_month_says_so(self) -> None:
        _, printed = run(cli.show_statement, ["1", "09/2026"], self.book)
        self.assertIn("No transactions this month.", printed)

    def test_spending_lists_the_largest_category_first_with_a_total(self) -> None:
        _, printed = run(cli.show_spending, ["10/2026"], self.book)
        lines = printed.splitlines()
        self.assertTrue(lines[2].startswith("Housing"))
        self.assertIn("$1,439.35", lines[-1])


class TestMain(unittest.TestCase):
    """The menu loop keeps going after a bad choice or a refused action."""

    @patch("ledger.cli.setup_logging")
    @patch("ledger.cli.storage.load_book", return_value=Book())
    def test_bad_choice_and_refused_action_return_to_the_menu(
        self, _load, _logging
    ) -> None:
        _, printed = run(cli.main, ["x", "3", "q"])
        self.assertIn("Please choose one of the numbers shown", printed)
        self.assertIn("There are no accounts yet", printed)
        self.assertIn("Goodbye.", printed)


if __name__ == "__main__":
    unittest.main()
