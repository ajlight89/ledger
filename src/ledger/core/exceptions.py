"""Exception hieracrchy for Ledger's core package.

Every error that Ledger raises on purpose derives from LedgerError, so a
caller (the GUI, a test, a script) can catch all of Ledger's own errors
with a single ``except LedgerError`` while unexpected bugs still surface.

This is the minimal set that Money needs. Errors for accounts, CSV import
and storage will be added when that code is written.
"""


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