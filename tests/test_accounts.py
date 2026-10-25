"""Tests for transactions, the Account base class and the three account types."""

import unittest
from datetime import date
from decimal import Decimal

from ledger.core.accounts import (
    Account,
    CheckingAccount,
    CreditCardAccount,
    SavingsAccount,
)
from ledger.core.categories import Category
from ledger.core.exceptions import (
    CreditLimitExceededError,
    InsufficientFundsError,
    InvalidAmountError,
    ValidationError,
)
from ledger.core.mixins import OverdraftMixin
from ledger.core.money import Money
from ledger.core.transaction import Transaction, TransactionKind

OPENED = date(2026, 10, 1)


def spend(account: Account, amount: str) -> Transaction:
    """Withdraw amount from account as a shopping expense."""
    return account.withdraw(
        Money.from_str(amount), OPENED, Category.SHOPPING, "Test purchase"
    )


class TestTransaction(unittest.TestCase):
    """A Transaction checks its own rules when it is created."""

    def test_a_zero_amount_is_refused(self) -> None:
        with self.assertRaises(InvalidAmountError):
            Transaction(
                date=OPENED,
                amount=Money.zero(),
                kind=TransactionKind.DEPOSIT,
                category=Category.INCOME,
                description="Paycheck",
            )


class TestAccount(unittest.TestCase):
    """Rules shared by every account type."""

    def test_account_itself_cannot_be_created(self) -> None:
        with self.assertRaises(TypeError):
            Account("Plain", OPENED)

    def test_a_blank_name_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            SavingsAccount("   ", OPENED)

    def test_withdrawing_below_zero_raises_insufficient_funds(self) -> None:
        savings = SavingsAccount("Savings", OPENED)
        savings.deposit(Money(100), OPENED, Category.INCOME, "Paycheck")
        with self.assertRaises(InsufficientFundsError):
            spend(savings, "100.01")
        self.assertEqual(savings.balance, Money(100))


class TestCheckingAccount(unittest.TestCase):
    """Checking adds an overdraft toggle through OverdraftMixin."""

    def test_overdraft_allows_minus_500_and_no_lower(self) -> None:
        checking = CheckingAccount("Checking", OPENED, overdraft_enabled=True)
        spend(checking, "500.00")
        self.assertEqual(checking.balance, Money(-500))
        with self.assertRaises(InsufficientFundsError):
            spend(checking, "0.01")

    def test_the_mixin_comes_before_account_in_the_mro(self) -> None:
        mro = CheckingAccount.__mro__
        self.assertLess(mro.index(OverdraftMixin), mro.index(Account))


class TestSavingsAccount(unittest.TestCase):
    """Savings earns interest through InterestMixin."""

    def test_one_month_of_interest_is_posted(self) -> None:
        savings = SavingsAccount("Savings", OPENED, interest_rate=Decimal("12"))
        savings.deposit(Money(1000), OPENED, Category.INCOME, "Opening deposit")
        savings.accrue_interest(date(2026, 10, 31))
        # $1,000.00 x 12% / 12 months = $10.00
        self.assertEqual(savings.balance, Money(1010))


class TestCreditCardAccount(unittest.TestCase):
    """A card may be owed money up to its credit limit."""

    def test_a_charge_past_the_limit_raises_credit_limit_exceeded(self) -> None:
        card = CreditCardAccount("Visa", OPENED, credit_limit=Money(2000))
        spend(card, "2000.00")
        with self.assertRaises(CreditLimitExceededError):
            spend(card, "0.01")
        self.assertEqual(card.balance, Money(-2000))


if __name__ == "__main__":
    unittest.main()
