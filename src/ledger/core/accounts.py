"""Account types: the abstract base class Account and the concrete accounts.

Sign convention, the same for every account: a positive balance is money
you have, and a negative balance is money you owe. A credit card therefore
starts at $0.00, spending (withdraw) makes its balance negative, and a
payment (deposit) brings it back towards zero.

The balance is read-only from outside. It changes only through deposit()
and withdraw(), which validate the amount first.
"""

from abc import ABC, abstractmethod
from decimal import Decimal

from ledger.core.exceptions import (
    CurrencyMismatchError,
    InsufficientFundsError,
    InvalidAccountSettingError,
    InvalidAmountError,
)
from ledger.core.mixins import InterestMixin, OverdraftProtectionMixin
from ledger.core.money import Money


class Account(ABC):
    """The shared base of every account type. It cannot be created on its own.
    
    Subclasses must provide ``account_type`` and ``available_funds()``.
    """

    def __init__(self, name: str, currency: str = "USD") -> None:
        self.name = name # goes through the name setter, so it is validated
        self._balance: Money = Money(0, currency) # Money validates the code

    # ------ properties --------------------------------------------

    @property
    def name(self) -> str:
        """The account's display name, such as 'Everyday'. Can be changed."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Accept non-empty text; surrounding spaces are removed."""
        if not isinstance(value, str) or not value.strip():
            raise InvalidAccountSettingError(
                f"Account name must be non-empty text, not {value!r}"
            )
        self._name: str = value.strip()

    @property
    def balance(self) -> Money:
        """The current balance. Read-only: use deposit() and withdraw()."""
        return self._balance

    @property
    def currency(self) -> str:
        """The account's three-letter currency code, such as 'USD'."""
        return self._balance.currency

    # ------ what every subclass must provide --------------------------------

    @property
    @abstractmethod
    def account_type(self) -> str:
        """A short label for users, such as 'Checking'."""

    @abstractmethod
    def available_funds(self) -> Money:
        """The most that can be withdrawn right now."""

    # ------ operations --------------------------------------------

    def deposit(self, amount: Money) -> None:
        """Add a positive amount to the balance."""
        self._check_amount(amount)
        self._balance += amount

    def withdraw(self, amount: Money) -> None:
        """Take a positive amount from the balance.
        
        Raises InsufficientFundsError if the amount is more than
        available_funds(); the balance is then left unchanged.
        """
        self._check_amount(amount)
        available = self.available_funds()
        if amount > available:
            raise InsufficientFundsError(amount, available)
        self._balance -= amount

    # ------ protected helpers, used by subclasses and mixins ----------------

    def _check_amount(self, amount: Money) -> None:
        """Raise unless amount is Money in this currency and more than zero."""
        if not isinstance(amount, Money):
            raise TypeError(f"Amount must be Money, not {type(amount).__name__}")
        if amount.currency != self.currency:
            raise CurrencyMismatchError(self.currency, amount.currency)
        if amount.amount <= 0:
            raise InvalidAmountError(f"Amount must be more than zero, not {amount}")

    def _check_limit(self, limit: Money, label: str) -> Money:
        """Return limit if it is Money in this currency and zero or more."""
        if not isinstance(limit, Money):
            raise TypeError(f"{label} must be Money, not {type(limit).__name__}")
        if limit.currency != self.currency:
            raise CurrencyMismatchError(self.currency, limit.currency)
        if limit.amount < 0:
            raise InvalidAccountSettingError(
                f"{label} cannot be negative, not {limit}"
            )
        return limit

    # ------ text representations --------------------------------------------

    def __repr__(self) -> str:
        """Developer form: <CheckingAccount 'Everyday' balance=Money('0.00', 'USD')>."""
        return f"<{type(self).__name__} {self.name!r} balance={self.balance!r}>"

    def __str__(self) -> str:
        """User form: Everyday (Checking): $120.00."""
        return f"{self.name} ({self.account_type}): {self.balance}"


class CheckingAccount(OverdraftProtectionMixin, Account):
    """An everyday account. The overdraft limit defaults to zero (no overdraft).
    
    available_funds() comes from OverdraftProtectionMixin, which is found
    before Account in the method resolution order.
    """

    def __init__(
            self,
            name: str,
            overdraft_limit: Money | None = None,
            currency: str = "USD",
    ) -> None:
        super().__init__(name, currency)
        if overdraft_limit is None:
            overdraft_limit = Money(0, self.currency)
        self.overdraft_limit = overdraft_limit  # validated by the mixin's setter

    @property
    def account_type(self) -> str:
        return "Checking"


class SavingsAccount(InterestMixin, Account):
    """A savings account that earns interest and cannot go below zero."""

    def __init__(
            self,
            name: str,
            interest_rate: Decimal,
            currency: str = "USD",
    ) -> None:
        super().__init__(name, currency)
        self.interest_rate = interest_rate  # validated by the mixin's setter

    @property
    def account_type(self) -> str:
        return "Savings"

    def available_funds(self) -> Money:
        """The balance: a savings account cannot be overdrawn."""
        return self.balance

    
class CreditCardAccount(Account):
    """A credit card. Spending is allowed until the amount owed reaches the credit limit."""

    def __init__(
            self,
            name: str,
            credit_limit: Money,
            currency: str = "USD",
    ) -> None:
        super().__init__(name, currency)
        self.credit_limit = credit_limit  # validated by the setter below

    @property
    def account_type(self) -> str:
        return "Credit card"

    @property
    def credit_limit(self) -> Money:
        """The most that can be owed on the card."""
        return self._credit_limit

    @credit_limit.setter
    def credit_limit(self, limit: Money) -> None:
        """Accept a Money of zero or more in the card's currency."""
        self._credit_limit: Money = self._check_limit(limit, "Credit limit")

    def available_funds(self) -> Money:
        """The credit still unused: the limit plus the (zero or negative) balance."""
        return self.balance + self._credit_limit