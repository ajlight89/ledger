"""Tests for the tkinter window. Window tests are skipped when there is no display."""

import tkinter as tk
import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from ledger.core.accounts import CheckingAccount, CreditCardAccount, SavingsAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import (
    AccountNotEmptyError,
    DuplicateAccountError,
    InsufficientFundsError,
    InvalidAmountError,
    ValidationError,
)
from ledger.core.money import Money
from ledger.gui.app import LedgerApp, parse_date, parse_money, parse_rate

OPENED = date(2026, 10, 1)


class TestParsing(unittest.TestCase):
    """The text-to-value helpers need no window, so these run everywhere."""

    def test_parse_money_accepts_dollar_sign_and_commas(self):
        self.assertEqual(parse_money(" $1,200.50 "), Money.from_str("1200.50"))

    def test_parse_money_refuses_text(self):
        with self.assertRaises(InvalidAmountError):
            parse_money("lots")

    def test_parse_rate_accepts_percent_sign(self):
        self.assertEqual(parse_rate("4.5%"), Decimal("4.5"))

    def test_parse_rate_refuses_text(self):
        with self.assertRaises(ValidationError):
            parse_rate("lots")

    def test_parse_date_blank_means_today(self):
        self.assertEqual(parse_date("  "), date.today())

    def test_parse_date_reads_month_day_year(self):
        self.assertEqual(parse_date("11/05/2026"), date(2026, 11, 5))

    def test_parse_date_refuses_other_formats(self):
        with self.assertRaises(ValidationError):
            parse_date("2026-11-05")


class GuiTestCase(unittest.TestCase):
    """Creates a hidden window for each test and a book with two accounts."""

    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("No display available for tkinter.")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

        # Replace save_book so tests never touch the real data file.
        patcher = patch("ledger.gui.app.storage.save_book")
        self.save = patcher.start()
        self.addCleanup(patcher.stop)

        self.book = Book()
        self.checking = CheckingAccount("Everyday", OPENED)
        self.checking.deposit(Money.from_str("100.00"), OPENED, Category.INCOME, "Pay")
        self.savings = SavingsAccount("Rainy Day", OPENED)
        self.book.add_account(self.checking)
        self.book.add_account(self.savings)
        self.app = LedgerApp(self.root, self.book)


class TestAccountList(GuiTestCase):
    def test_list_shows_each_active_account(self):
        rows = self.app.tree.get_children()
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            self.app.tree.item(rows[0], "values"),
            ("Everyday", "Checking", "$100.00"),
        )

    def test_every_second_row_is_striped(self):
        first, second = self.app.tree.get_children()
        self.assertFalse(self.app.tree.tag_has("odd", first))
        self.assertTrue(self.app.tree.tag_has("odd", second))

    def test_refresh_drops_archived_accounts(self):
        self.book.archive_account(self.savings.id)
        self.app.refresh()
        self.assertEqual(len(self.app.tree.get_children()), 1)


class TestOpenAccount(GuiTestCase):
    def test_opens_savings_with_rate_saves_and_selects_it(self):
        self.app.open_account("Savings", "Vacation", False, "4.5%", "")
        account = self.book.accounts[-1]
        self.assertIsInstance(account, SavingsAccount)
        self.assertEqual(account.interest_rate, Decimal("4.5"))
        self.save.assert_called_once_with(self.book)
        self.assertEqual(len(self.app.tree.get_children()), 3)
        self.assertEqual(self.app.tree.selection(), (str(account.id),))

    def test_opens_credit_card_with_limit(self):
        self.app.open_account("Credit Card", "Visa", False, "19.99", "$2,000")
        card = self.book.accounts[-1]
        self.assertIsInstance(card, CreditCardAccount)
        self.assertEqual(card.credit_limit, Money.from_str("2000"))

    def test_taken_name_changes_nothing(self):
        with self.assertRaises(DuplicateAccountError):
            self.app.open_account("Checking", "everyday", False, "0", "")
        self.assertEqual(len(self.book.accounts), 2)
        self.save.assert_not_called()

    def test_bad_rate_adds_nothing(self):
        with self.assertRaises(ValidationError):
            self.app.open_account("Savings", "Vacation", False, "lots", "")
        self.assertEqual(len(self.book.accounts), 2)
        self.save.assert_not_called()


class TestDepositWithdraw(GuiTestCase):
    def test_selected_account_needs_a_selection(self):
        with self.assertRaises(ValidationError):
            self.app.selected_account()

    def test_selected_account_returns_the_selected_one(self):
        self.app.tree.selection_set(str(self.savings.id))
        self.assertIs(self.app.selected_account(), self.savings)

    def test_deposit_button_without_selection_shows_a_message(self):
        with patch("ledger.gui.app.messagebox.showerror") as showerror:
            self.app.show_deposit()
        showerror.assert_called_once()

    def test_deposit_updates_the_row_keeps_selection_and_saves(self):
        row = str(self.checking.id)
        self.app.tree.selection_set(row)
        self.app.record_transaction(
            self.checking.deposit, "$50", "11/01/2026", "Income", "Gift"
        )
        self.assertEqual(self.checking.balance, Money.from_str("150.00"))
        self.assertEqual(self.app.tree.item(row, "values")[2], "$150.00")
        self.assertEqual(self.app.tree.selection(), (row,))
        self.save.assert_called_once_with(self.book)

    def test_refused_withdrawal_records_nothing(self):
        with self.assertRaises(InsufficientFundsError):
            self.app.record_transaction(
                self.checking.withdraw, "500", "", "Other", "New TV"
            )
        self.assertEqual(self.checking.balance, Money.from_str("100.00"))
        self.save.assert_not_called()

    def test_blank_description_is_refused(self):
        with self.assertRaises(ValidationError):
            self.app.record_transaction(self.checking.deposit, "5", "", "Income", "  ")
        self.save.assert_not_called()


class TestTransferRename(GuiTestCase):
    def test_transfer_moves_money_and_saves(self):
        self.app.transfer(self.checking, self.savings, "40", "", "To savings")
        self.assertEqual(self.checking.balance, Money.from_str("60.00"))
        self.assertEqual(self.savings.balance, Money.from_str("40.00"))
        self.save.assert_called_once_with(self.book)

    def test_refused_transfer_moves_nothing(self):
        with self.assertRaises(InsufficientFundsError):
            self.app.transfer(self.checking, self.savings, "500", "", "Too much")
        self.assertEqual(self.checking.balance, Money.from_str("100.00"))
        self.assertEqual(self.savings.balance, Money.zero())
        self.save.assert_not_called()

    def test_transfer_to_the_same_account_is_refused(self):
        with self.assertRaises(ValidationError):
            self.app.transfer(self.checking, self.checking, "10", "", "Loop")
        self.save.assert_not_called()

    def test_transfer_button_needs_two_accounts(self):
        self.book.archive_account(self.savings.id)
        self.app.refresh()
        self.app.tree.selection_set(str(self.checking.id))
        with patch("ledger.gui.app.messagebox.showerror") as showerror:
            self.app.show_transfer()
        showerror.assert_called_once()

    def test_rename_updates_the_row_and_saves(self):
        self.app.rename_account(self.checking, "Main")
        self.assertEqual(self.checking.name, "Main")
        self.assertEqual(self.app.tree.item(str(self.checking.id), "values")[0], "Main")
        self.save.assert_called_once_with(self.book)

    def test_rename_to_a_taken_name_changes_nothing(self):
        with self.assertRaises(DuplicateAccountError):
            self.app.rename_account(self.checking, "rainy day")
        self.assertEqual(self.checking.name, "Everyday")
        self.save.assert_not_called()


class TestArchiveRestore(GuiTestCase):
    def show_archived(self):
        """Tick the "Show archived accounts" box, as a click would."""
        self.app.show_archived.set(True)
        self.app.change_view()

    def test_archive_empty_account_removes_its_row_and_saves(self):
        self.app.archive_account(self.savings)
        self.assertIn(self.savings, self.book.archived_accounts)
        self.assertEqual(self.app.tree.get_children(), (str(self.checking.id),))
        self.save.assert_called_once_with(self.book)

    def test_archive_account_with_money_is_refused(self):
        with self.assertRaises(AccountNotEmptyError):
            self.app.archive_account(self.checking)
        self.assertIn(self.checking, self.book.accounts)
        self.save.assert_not_called()

    def test_archived_view_lists_only_archived_accounts(self):
        self.book.archive_account(self.savings.id)
        self.show_archived()
        self.assertEqual(self.app.tree.get_children(), (str(self.savings.id),))
        self.app.tree.selection_set(str(self.savings.id))
        self.assertIs(self.app.selected_account(), self.savings)

    def test_restore_brings_the_account_back(self):
        self.book.archive_account(self.savings.id)
        self.show_archived()
        self.app.restore_account(self.savings)
        self.assertIn(self.savings, self.book.accounts)
        self.assertEqual(self.app.tree.get_children(), ())
        self.save.assert_called_once_with(self.book)

    def test_restore_under_a_new_name_after_a_clash(self):
        self.book.archive_account(self.savings.id)
        self.book.add_account(SavingsAccount("Rainy Day", OPENED))
        with self.assertRaises(DuplicateAccountError):
            self.app.restore_account(self.savings)
        self.app.restore_account(self.savings, "Old Rainy Day")
        self.assertEqual(self.savings.name, "Old Rainy Day")
        self.assertIn(self.savings, self.book.accounts)

    def test_refused_new_name_puts_the_old_name_back(self):
        self.book.archive_account(self.savings.id)
        self.book.add_account(SavingsAccount("Rainy Day", OPENED))
        with self.assertRaises(DuplicateAccountError):
            self.app.restore_account(self.savings, "everyday")
        self.assertEqual(self.savings.name, "Rainy Day")
        self.assertIn(self.savings, self.book.archived_accounts)
        self.save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
