"""Money: an exact amount of money in one currency.

Amounts are Decimal values built from strings, integers or Decimals, never
from floats (a float cannot store most cent values exactly, so rejecting it
keeps every amount accurate and consistent). Amounts are rounded once, when
the object is created, to whole cents using ROUND_HALF_UP. Money is
immutable: once created, its amount and currency never change, and every
operation returns a new Money.
"""


from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering

from ledger.core.exceptions import (
    CurrencyMismatchError,
    InvalidAmountError,
    InvalidCurrencyError,
)

_CENT = Decimal("0.01")
_SYMBOLS: dict[str, str] = {"USD": "$", "EUR": "€", "GBP": "£"}


@total_ordering
class Money:
    "An exact, immutable amount of money in a single currency."

    __slots__ = ("_amount", "_currency")

    def __init__(self, amount: Decimal | int | str, currency: str = "USD") -> None:
        self._amount: Decimal = self._to_cents(amount)
        self._currency: str = self._check_currency(currency)

    # ------ validation helpers --------------------------------------------

    @staticmethod
    def _to_cents(value: Decimal | int | str) -> Decimal:
        """Convert value to a Decimal rounded to cents, or raise exception."""
        # bool is a subclass of int, so it must be rejected first.
        if isinstance(value, bool) or not isinstance(value, (str, int, Decimal)):
            raise InvalidAmountError(
                f"Amount must be a str, int or Decimal, not {type(value).__name__}"
            )
        try:
            number = Decimal(value)
        except InvalidOperation as err:
            raise InvalidAmountError(f"Not a number: {value!r}") from err
        if not number.is_finite():
            raise InvalidAmountError(f"Amount must be a finite number, not {value!r}")
        try:
            cents = number.quantize(_CENT, rounding=ROUND_HALF_UP)
        except InvalidOperation as err:
            raise InvalidAmountError(f"Amount is too large: {value!r}") from err
        if cents.is_zero():
            return abs(cents) # turns -0.00 into 0.00 so it never prints as "-0.00"
        return cents

    @staticmethod
    def _check_currency(code: str) -> str:
        """Return code in upper case if it is three ASCII letters, or raise exception."""
        if not (
            isinstance(code, str)
            and len(code) == 3
            and code.isascii()
            and code.isalpha()
        ):
            raise InvalidCurrencyError(
                f"Currency must be a three-letter code like 'USD', not {code!r}"
            )
        return code.upper()

    # ------ read-only properties --------------------------------------------

    @property
    def amount(self) -> Decimal:
        """The amount, rounded to cents. Read-only."""
        return self._amount

    @property
    def currency(self) -> str:
        """The three-letter currency code ('USD'), in upper case. Read-only."""
        return self._currency

    # ------ text representations --------------------------------------------

    def __repr__(self) -> str:
        """Unambiguous form for developers: Money('19.99', 'USD')."""
        return f"Money({str(self._amount)!r}, {self._currency!r})"

    def __str__(self) -> str:
        """Friendly form for users: $1,234.56, -$42.17 or 10.00 CAD."""
        sign = "-" if self._amount < 0 else ""
        digits = f"{abs(self._amount):,.2f}"
        symbol = _SYMBOLS.get(self._currency)
        if symbol is None:
            return f"{sign}{digits} {self._currency}"
        return f"{sign}{symbol}{digits}"

    # ------ equality and hashing --------------------------------------------

    def __eq__(self, other: object) -> bool:
        """Money values are equal when both amount and currency match.
        
        Comparing with anything that is not Money returns NotImplemented,
        so Python can ask the other operand and then fall back to False.
        Different currencies are simply unequal; == never raises.
        """
        if not isinstance(other, Money):
            return NotImplemented
        return self._amount == other._amount and self._currency == other._currency

    def __hash__(self) -> int:
        """Hash the same fields __eq__ compares, so equal Money hash equal."""
        return hash((self._amount, self._currency))

    # ------ arithmetic --------------------------------------------

    def _check_same_currency(self, other: "Money") -> None:
        """Raise CurrencyMismatchError unless other uses this currency."""
        if self._currency != other._currency:
            raise CurrencyMismatchError(self._currency, other._currency)

    def __add__(self, other: "Money") -> "Money":
        """Money + Money in the same currency."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return Money(self._amount + other._amount, self._currency)

    def __sub__(self, other: "Money") -> "Money":
        """Money - Money in the same currency."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return Money(self._amount - other._amount, self._currency)

    def __neg__(self) -> "Money":
        """-Money: the same amount with the opposite sign."""
        return Money(-self._amount, self._currency)

    def __mul__(self, factor: int | Decimal) -> "Money":
        """Money * int or Money * Decimal, rounded half up to cents.
        
        Floats, bools and Money are refused: Money * Money has no meaning
        (dollars times dollars is not money).
        """
        if isinstance(factor, bool) or not isinstance(factor, (int, Decimal)):
            return NotImplemented
        return Money(self._amount * factor, self._currency)

    def __rmul__(self, factor: int | Decimal) -> "Money":
        """int * Money or Decimal * Money, the same as Money * factor."""
        return self.__mul__(factor)

# ------ ordering --------------------------------------------

    def __lt__(self, other: "Money") -> bool:
        """Money < Money in the same currency.
        
        @total_ordering derives <=, > and >= from this method and __eq__.
        Unlike ==, ordering different currencies raises, because there is
        no right answer to "is 1 USD less than 1 EUR?
        """

        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self._amount < other._amount
    