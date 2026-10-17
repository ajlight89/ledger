"""Tests for the mixins, through the accounts that use them.

CheckingAccount uses OverdraftProtectionMixin and SavingsAccount uses
InterestMixin.
"""

import unittest
from decimal import Decimal

from ledger.core.accounts import Account, CheckingAccount, SavingsAccount
from ledger.core.exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
    InvalidAccountSettingError,
)
from ledger.core.mixins import InterestMixin, OverdraftProtectionMixin
from ledger.core.money import Money


class MethodResolutionOrderTest(unittest.TestCase):
    def test_checking_finds_mixin_before_account(self) -> None:
        self.assertEqual(
            CheckingAccount.__mro__[:3],
            (CheckingAccount, OverdraftProtectionMixin, Account)
        )

    def test_checking_uses_the_mixins_available_funds(self) -> None:
        self.assertIs(
            CheckingAccount.available_funds, OverdraftProtectionMixin.available_funds
        )

    def test_savings_finds_mixin_before_account(self) -> None:
        self.assertEqual(
            SavingsAccount.__mro__[:3],
            (SavingsAccount, InterestMixin, Account)
        )

    def test_both_are_accounts(self) -> None:
        self.assertIsInstance(CheckingAccount("Everyday"), Account)
        self.assertIsInstance(SavingsAccount("Rainy day", Decimal("0.04")), Account)


class CheckingAccountTest(unittest.TestCase):
    def test_account_type(self) -> None:
        self.assertEqual(CheckingAccount("Everyday").account_type, "Checking")

    def test_overdraft_limit_defaults_to_zero(self) -> None:
        checking = CheckingAccount("Everyday")
        self.assertEqual(checking.overdraft_limit, Money("0"))

    def test_default_limit_uses_the_account_currency(self) -> None:
        checking = CheckingAccount("Girokonto", currency="EUR")
        self.assertEqual(checking.overdraft_limit, Money("0", "EUR"))

    def test_without_overdraft_cannot_go_below_zero(self) -> None:
        checking = CheckingAccount("Everyday")
        checking.deposit(Money("50"))
        with self.assertRaises(InsufficientFundsError):
            checking.withdraw(Money("50.01"))
        self.assertEqual(checking.balance, Money("50"))

    def test_overdraft_allows_going_below_zero_up_to_the_limit(self) -> None:
        checking = CheckingAccount("Everyday", overdraft_limit=Money("100"))
        checking.deposit(Money("50"))
        self.assertEqual(checking.available_funds(), Money("150"))
        checking.withdraw(Money("150"))
        self.assertEqual(checking.balance, Money("-100"))

    def test_withdrawal_past_the_overdraft_limit_raises(self) -> None:
        checking = CheckingAccount("Everyday", overdraft_limit=Money("100"))
        with self.assertRaises(InsufficientFundsError) as caught:
            checking.withdraw(Money("100.01"))
        self.assertEqual(caught.exception.available, Money("100"))
        self.assertEqual(checking.balance, Money("0"))

    def test_overdraft_limit_can_be_changed(self) -> None:
        checking = CheckingAccount("Everyday")
        checking.overdraft_limit = Money("250")
        self.assertEqual(checking.available_funds(), Money("250"))

    def test_rejects_negative_overdraft_limit(self) -> None:
        with self.assertRaises(InvalidAccountSettingError):
            CheckingAccount("Everyday", overdraft_limit=Money("-1"))

    def test_rejects_overdraft_limit_in_other_currency(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            CheckingAccount("Everyday", overdraft_limit=Money("100", "EUR"))


class SavingsAccountTest(unittest.TestCase):
    def test_account_type(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.04"))
        self.assertEqual(savings.account_type, "Savings")

    def test_cannot_go_below_zero(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.04"))
        savings.deposit(Money("10"))
        with self.assertRaises(InsufficientFundsError):
            savings.withdraw(Money("10.01"))
        self.assertEqual(savings.available_funds(), Money("10"))

    def test_interest_rate_is_stored(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.045"))
        self.assertEqual(savings.interest_rate, Decimal("0.045"))

    def test_accepts_rates_from_zero_to_one(self) -> None:
        for rate in ("0", "0.5", "1"):
            with self.subTest(rate=rate):
                savings = SavingsAccount("Rainy day", Decimal(rate))
                self.assertEqual(savings.interest_rate, Decimal(rate))

    def test_rejectss_rates_outside_zero_to_one(self) -> None:
        for bad in ("-0.01", "1.01", "4.5"):
            with self.subTest(bad=bad), self.assertRaises(InvalidAccountSettingError):
                SavingsAccount("Rainy day", Decimal(bad))

    def test_rejects_rates_that_are_not_finite_decimals(self) -> None:
        for bad in (0.04, "0.04", 0, None, Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(bad=bad), self.assertRaises(InvalidAccountSettingError):
                SavingsAccount("Rainy day", bad)  # type: ignore[arg-type]

    def test_rejected_rate_change_keeps_old_rate(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.04"))
        with self.assertRaises(InvalidAccountSettingError):
            savings.interest_rate = Decimal(2)
        self.assertEqual(savings.interest_rate, Decimal("0.04"))


class InterestTest(unittest.TestCase):
    def test_monthly_interest_is_a_twelfth_of_the_yearly_rate(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.06"))
        savings.deposit(Money("1000"))
        self.assertEqual(savings.monthly_interest(), Money("5.00"))

    def test_monthly_interest_rounds_half_up_to_cents(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.05"))
        savings.deposit(Money("1000"))
        # 1000 * 0.05 / 12 = 4.1666..., which rounds to 4.17
        self.assertEqual(savings.monthly_interest(), Money("4.17"))

    def test_no_interest_on_an_empty_account(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.05"))
        self.assertEqual(savings.monthly_interest(), Money("0"))

    def test_apply_monthly_interest_deposits_it(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal("0.06"))
        savings.deposit(Money("1000"))
        added = savings.apply_monthly_interest()
        self.assertEqual(added, Money("5"))
        self.assertEqual(savings.balance, Money("1005"))

    def test_applying_zero_interest_changes_nothing(self) -> None:
        savings = SavingsAccount("Rainy day", Decimal(0))
        savings.deposit(Money("1000"))
        self.assertEqual(savings.apply_monthly_interest(), Money("0"))
        self.assertEqual(savings.balance, Money("1000"))

    def test_interest_is_in_the_account_currency(self) -> None:
        savings = SavingsAccount("Sparkonto", Decimal("0.06"), "EUR")
        savings.deposit(Money("1000", "EUR"))
        self.assertEqual(savings.monthly_interest(), Money("5", "EUR"))


if __name__ == "__main__":
    unittest.main()