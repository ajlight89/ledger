"""Tests for monthly statements, spending by category and CSV import."""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from ledger.core.accounts import CheckingAccount, SavingsAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import CsvFormatError, ValidationError
from ledger.core.importer import guess_category, import_csv
from ledger.core.money import Money
from ledger.core.reports import spending_by_category, statement_lines

OPENED = date(2026, 9, 1)
SAMPLE = Path(__file__).parent.parent / "sample.csv"


class TestReports(unittest.TestCase):
    """Statements list a month's transactions; spending totals each category."""

    def setUp(self) -> None:
        self.book = Book()
        self.checking = self.book.add_account(CheckingAccount("Checking", OPENED))
        self.savings = self.book.add_account(SavingsAccount("Savings", OPENED))
        dining = Category.DINING_OUT
        self.checking.deposit(Money(500), date(2026, 9, 15), Category.INCOME, "Pay")
        self.checking.withdraw(Money(40), date(2026, 10, 3), dining, "Pizza")
        self.checking.withdraw(Money(60), date(2026, 10, 9), dining, "Cafe")
        self.checking.withdraw(Money(25), date(2026, 10, 5), Category.SHOPPING, "Shoes")
        self.book.transfer(
            Money(100), self.checking.id, self.savings.id, date(2026, 10, 10), "Save"
        )

    def test_a_statement_keeps_a_running_balance_in_date_order(self) -> None:
        lines = list(statement_lines(self.checking, 2026, 10))
        self.assertEqual(
            [(line.description, line.balance) for line in lines],
            [
                ("Pizza", Money(460)),
                ("Shoes", Money(435)),
                ("Cafe", Money(375)),
                ("Save", Money(275)),
            ],
        )

    def test_a_bad_month_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            list(statement_lines(self.checking, 2026, 13))

    def test_spending_leaves_out_income_and_transfers(self) -> None:
        self.assertEqual(
            spending_by_category(self.book, 2026, 10),
            {Category.DINING_OUT: Money(100), Category.SHOPPING: Money(25)},
        )


class TestImportCsv(unittest.TestCase):
    """Rows from a bank CSV file become transactions in an account."""

    def setUp(self) -> None:
        self.account = CheckingAccount("Checking", OPENED)

    def test_the_sample_file_imports_every_row(self) -> None:
        added = import_csv(self.account, SAMPLE)
        self.assertEqual(len(added), 15)
        self.assertEqual(self.account.balance, Money.from_str("1460.65"))
        self.assertEqual(added[0].category, Category.INCOME)
        self.assertEqual(added[2].category, Category.FOOD_GROCERIES)

    def test_only_whole_words_pick_a_category(self) -> None:
        self.assertEqual(guess_category("CITY BUS"), Category.TRANSPORTATION)
        self.assertEqual(guess_category("SMALL BUSINESS LLC"), Category.OTHER)

    def test_importing_the_same_file_twice_adds_nothing_new(self) -> None:
        import_csv(self.account, SAMPLE)
        self.assertEqual(import_csv(self.account, SAMPLE), [])
        self.assertEqual(len(self.account.transactions), 15)

    def test_a_bad_row_adds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text(
                "Date,Description,Amount\n"
                "10/01/2026,PAYROLL DEPOSIT,1450.00\n"
                "10/02/2026,CORNER GROCERY,abc\n",
                encoding="utf-8",
            )
            with self.assertRaises(CsvFormatError):
                import_csv(self.account, path)
        self.assertEqual(self.account.transactions, ())
