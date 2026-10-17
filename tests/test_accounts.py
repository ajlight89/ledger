"""Tests for the Account base class and CreditCardAccount."""

import unittest

from ledger.core.accounts import Account, CreditCardAccount
from ledger.core.exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
    InvalidAccountSettingError,
    InvalidAmountError,
    InvalidCurrencyError,
)
from ledger.core.money import Money


def make_card(limit: str = "500") -> CreditCardAccount:
    """A fresh USD credit card with the given limit."""
    return CreditCardAccount("Visa", Money(limit))


class AbstractBaseClassTest(unittest.TestCase):
    def test_account_cannot_be_created_directly(self) -> None:
        with self.assertRaises(TypeError):
            Account("Plain")  #type: ignore[abstract]

    def test_subclass_missing_an_abstract_method_cannot_be_created(self) -> None:
        class Incomplete(Account):
            @property
            def account_type(self) -> str:
                return "Incomplete"

        with self.assertRaises(TypeError):
            Incomplete("Half done")  # type: ignore[abstract]

    def test_credit_card_is_an_account(self) -> None:
        self.assertIsInstance(make_card(), Account)


class NamePropertyTest(unittest.TestCase):
    def test_name_is_stripped(self) -> None:
        self.assertEqual(CreditCardAccount(" Visa ", Money("1")).name, "Visa")

    def test_name_can_be_changed(self) -> None:
        card = make_card()
        card.name = "Travel card"
        self.assertEqual(card.name, "Travel card")

    def test_rejects_empty_or_non_text_names(self) -> None:
        for bad in ("", " ", None, 42):
            with self.subTest(bad=bad), self.assertRaises(InvalidAccountSettingError):
                CreditCardAccount(bad, Money("1"))  # type: ignore[arg-type]

    def test_rejected_rename_keeps_old_name(self) -> None:
        card = make_card()
        with self.assertRaises(InvalidAccountSettingError):
            card.name = ""
        self.assertEqual(card.name, "Visa")


class BalanceAndCurrencyTest(unittest.TestCase):
    def test_new_account_starts_at_zero(self) -> None:
        self.assertEqual(make_card().balance, Money("0"))

    def test_balance_is_read_only(self) -> None:
        card = make_card()
        with self.assertRaises(AttributeError):
            card.balance = Money("1000")  # type: ignore[misc]

    def test_currency_defaults_to_usd_and_can_be_set(self) -> None:
        self.assertEqual(make_card().currency, "USD")
        euro_card = CreditCardAccount("Euro card", Money("100", "EUR"), "eur")
        self.assertEqual(euro_card.currency, "EUR")

    def test_rejects_bad_currency_code(self) -> None:
        with self.assertRaises(InvalidCurrencyError):
            CreditCardAccount("Visa", Money("100"), "dollars")


class DepositTest(unittest.TestCase):
    def test_deposit_adds_to_balance(self) -> None:
        card = make_card()
        card.deposit(Money("20"))
        card.deposit(Money("5.50"))
        self.assertEqual(card.balance, Money("25.50"))

    def test_rejects_zero_or_negative_amounts(self) -> None:
        card = make_card()
        for bad in ("0", "-5"):
            with self.subTest(bad=bad), self.assertRaises(InvalidAmountError):
                card.deposit(Money(bad))
        self.assertEqual(card.balance, Money("0"))

    def test_rejects_other_currency(self) -> None:
        card = make_card()
        with self.assertRaises(CurrencyMismatchError):
            card.deposit(Money("5", "EUR"))

    def test_rejects_values_that_are_not_money(self) -> None:
        card = make_card()
        for bad in (5, "5", None):
            with self.subTest(bad=bad), self.assertRaises(TypeError):
                card.deposit(bad)  # type: ignore[arg-type]


class WithdrawTest(unittest.TestCase):
    def test_withdraw_subtracts_from_balance(self) -> None:
        card = make_card()
        card.withdraw(Money("45"))
        self.assertEqual(card.balance, Money("-45"))

    def test_rejects_zero_or_negative_amounts(self) -> None:
        card = make_card()
        for bad in ("0", "-5"):
            with self.subTest(bad=bad), self.assertRaises(InvalidAmountError):
                card.withdraw(Money(bad))

    def test_rejects_other_currency(self) -> None:
        card = make_card()
        with self.assertRaises(CurrencyMismatchError):
            card.withdraw(Money("5", "EUR"))

    def test_too_large_withdrawal_raises_and_leaves_balance_unchanged(self) -> None:
        card = make_card("100")
        card.withdraw(Money("30"))
        with self.assertRaises(InsufficientFundsError) as caught:
            card.withdraw(Money("70.01"))
        self.assertEqual(caught.exception.requested, Money("70.01"))
        self.assertEqual(caught.exception.available, Money("70"))
        self.assertEqual(card.balance, Money("-30"))


class CreditCardTest(unittest.TestCase):
    def test_account_type(self) -> None:
        self.assertEqual(make_card().account_type, "Credit card")

    def test_can_spend_exactly_up_to_the_limit(self) -> None:
        card = make_card("500")
        card.withdraw(Money("500"))
        self.assertEqual(card.balance, Money("-500"))
        self.assertEqual(card.available_funds(), Money("0"))

    def test_payment_restores_available_credit(self) -> None:
        card = make_card("500")
        card.withdraw(Money("200"))
        card.deposit(Money("150"))
        self.assertEqual(card.balance, Money("-50"))
        self.assertEqual(card.available_funds(), Money("450"))

    def test_credit_limit_can_be_changed(self) -> None:
        card = make_card("500")
        card.credit_limit = Money("1000")
        self.assertEqual(card.available_funds(), Money("1000"))

    def test_rejects_negative_credit_limit(self) -> None:
        with self.assertRaises(InvalidAccountSettingError):
            make_card("-1")

    def test_rejects_credit_limit_in_other_currency(self) -> None:
        with self.assertRaises(CurrencyMismatchError):
            CreditCardAccount("Visa", Money("500", "EUR"))

    def test_rejects_credit_limit_that_is_not_money(self) -> None:
        with self.assertRaises(TypeError):
            CreditCardAccount("Visa", 500)  # type: ignore[arg-type]


class TextTest(unittest.TestCase):
    def test_str_shows_name_type_and_balance(self) -> None:
        card = make_card()
        card.withdraw(Money("45"))
        self.assertEqual(str(card), "Visa (Credit card): -$45.00")

    def test_repr_shows_class_name_and_exact_balance(self) -> None:
        self.assertEqual(
            repr(make_card()), "<CreditCardAccount 'Visa' balance=Money('0.00', 'USD')>")


if __name__ == "__main__":
    unittest.main()