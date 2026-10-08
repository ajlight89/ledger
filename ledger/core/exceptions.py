"""Exceptions raised by the core when an operation cannot be completed.

Every exception here subclasses LedgerError, so the GUI can catch that one
class and show the message. Messages are written for the end user.
"""


class LedgerError(Exception):
    """Base class for every error the core reports to the user."""

    def __init__(self, message: str) -> None:
        """Create the error with a message written for the end user."""
        super().__init__(message)


class CurrencyMismatchError(LedgerError):
    """Money values in different currencies were combined or compared."""


class InvalidAmountError(LedgerError):
    """An amount was zero or negative where a positive one is required."""


class InsufficientFundsError(LedgerError):
    """A withdrawal would take an account below its minimum balance."""


class CreditLimitExceededError(LedgerError):
    """A charge would take a credit card past its credit limit."""


class AccountNotFoundError(LedgerError):
    """No account exists with the requested id or name."""


class DuplicateAccountError(LedgerError):
    """An account with the same name already exists."""


class ValidationError(LedgerError):
    """A property was given an invalid value, such as an empty name."""


class CsvFormatError(LedgerError):
    """A CSV file does not match the expected bank format."""


class StorageError(LedgerError):
    """The data file could not be read or written."""
