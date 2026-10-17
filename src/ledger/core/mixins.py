"""Mixins: small pieces of behavior that several account types can share.

A mixin is not an account by itself and is never created on its own. It is
listed before Account in a class's bases, as in
``class SavingsAccount(InterestMixin, Account)``, and adds its properties and
methods to that class. Python searches the bases from left to right (the
method resolution order, or MRO), so a mixin's method is found before
Account's.

These mixins have no __init__ of their own. The account class that uses a
mixin sets the mixin's property in its own __init__, and the property's
setter does the validation. Each mixin relies on members that Account
provides (balance, currency, deposit, and _check_limit); its docstring says
which.
"""


from decimal import Decimal

from ledger.core.exceptions import InvalidAccountSettingError
from ledger.core.money import Money

_MONTHS_PER_YEAR = 12


class InterestMixin:
    """Adds a yearly interest rate and monthly interest to an account.
    
    Relies on Account for ``balance``, ``currency`` and ``deposit()``.
    """

    _interest_rate: Decimal

    @property
    def interest_rate(self) -> Decimal:
        """The yearly interest rate as a fraction: Decimal("0.045") is 4.5%."""
        return self._interest_rate

    @interest_rate.setter
    def interest_rate(self, rate: Decimal) -> None:
        """Accept a finite Decimal from 0 to 1, or raise InvalidAccountSettingError."""
        if not isinstance(rate, Decimal) or not rate.is_finite():
            raise InvalidAccountSettingError(
                f"Interest rate must be a Decimal such as Decimal('0.045'), not {rate!r}"
            )
        if not Decimal(0) <= rate <= Decimal(1):
            raise InvalidAccountSettingError(
                f"Interest rate must be between 0 and 1 (0% to 100%), not {rate}"
            )
        self._interest_rate = rate

    def monthly_interest(self) -> Money:
        """One month's interest on the current balance, rounded to cents.
        
        Zero when the balance is zero or negative.
        """
        if self.balance.amount <= 0:
            return Money(0, self.currency)
        return self.balance * (self._interest_rate / _MONTHS_PER_YEAR)

    def apply_monthly_interest(self) -> Money:
        """Deposit one month's interest and return the amount added."""
        interest = self.monthly_interest()
        if interest.amount > 0:
            self.deposit(interest)
        return interest


class OverdraftProtectionMixin:
    """Lets the balance go below zero, down to an overdraft limit.
    
    Provides ``available_funds()``, which Account declares abstract, so an
    account using this mixin can withdraw its balance plus the limit.
    Relies on Account for ``balance`` and ``_check_limit()``.
    """

    _overdraft_limit: Money

    @property
    def overdraft_limit(self) -> Money:
        """How far below zero the balance may go. Zero means no overdraft."""
        return self._overdraft_limit

    @overdraft_limit.setter
    def overdraft_limit(self, limit: Money) -> None:
        """Accept a Money of zero or more in the account's currency."""
        self._overdraft_limit = self._check_limit(limit, "Overdraft limit")

    def available_funds(self) -> Money:
        """The balance plus the overdraft limit."""
        return self.balance + self._overdraft_limit