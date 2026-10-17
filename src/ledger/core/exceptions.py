"""Exception hieracrchy for Ledger's core package.

Every error that Ledger raises on purpose derives from LedgerError, so a
caller (the GUI, a test, a script) can catch all of Ledger's own errors
with a single ``except LedgerError`` while unexpected bugs still surface.

Money raises InvalidAmountError, InvalidCurrencyError and
CurrencyMismatchError. Accounts add InvalidAccountSettingError and
InsufficientFundsError. Errors for CSV import and storage will be added
when that code is written.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING: # imported only for type hints, so there is no import cycle
    from ledger.core.money import Money


class LedgerError(Exception):
    """Base class for every error Ledger raises deliberately."""



class InvalidAmountError(LedgerError):
    """A value cannot be used as an amount of money.

    Raised for the wrong type (Example: float), text that is not a
    number, or a non-finite Decimal such as NaN or Infinity.
    """



class InvalidCurrencyError(LedgerError):
    """A currency code is not three letters, like 'USD' or 'EUR'."""


    

class CurrencyMismatchError(LedgerError):
    """Two Money values in different currencies were combined or compared."""

    def __init__(self, left: str, right: str) -> None:
        super().__init__(f"Cannot combine {left} with {right}")
        self.left: str = left
        self.right: str = right


class InvalidAccountSettingError(LedgerError):
    """An account setting is not allowed.
    
    For example: an empty account name, a negative credit or overdraft
    limit, or an interest rate outside 0% to 100%.
    """


class InsufficientFundsError(LedgerError):
    """A withdrawal is larger than the money the account has available."""

    def __init__(self, requested: "Money", available: "Money") -> None:
        super().__init__(
            f"Cannot withdraw {requested}: only {available} is available"
        )
        self.requested: Money = requested
        self.available: Money = available