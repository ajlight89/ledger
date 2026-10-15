"""Decorators that add shared behavior to core methods."""

import logging
from functools import wraps

from ledger.core.exceptions import InvalidAmountError, LedgerError

logger = logging.getLogger(__name__)


def requires_positive_amount(method):
    """Reject a zero or negative amount before the method body runs.

    The decorated method must take the amount as its first argument after self.
    """

    @wraps(method)
    def wrapper(self, amount, *args, **kwargs):
        if amount.amount <= 0:
            raise InvalidAmountError(
                f"The amount must be more than $0.00, not {amount}."
            )
        return method(self, amount, *args, **kwargs)

    return wrapper


def logged(func):
    """Log each call and any exception it raises, then raise it again.

    A LedgerError is a problem the user can fix, so it is logged as a warning.
    Any other exception is a bug, so it is logged as an error with a traceback.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        name = func.__qualname__
        logger.info("Calling %s with args=%r kwargs=%r", name, args, kwargs)
        try:
            return func(*args, **kwargs)
        except LedgerError as err:
            logger.warning("%s refused: %s", name, err)
            raise
        except Exception:
            logger.exception("%s failed unexpectedly", name)
            raise

    return wrapper
