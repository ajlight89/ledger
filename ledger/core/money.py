"""Money: an exact, immutable amount in a single currency."""

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from functools import total_ordering

from ledger.core.exceptions import CurrencyMismatchError, InvalidAmountError

# Every amount is kept to whole cents.
CENT = Decimal("0.01")


@total_ordering
class Money:
    """An exact amount of money in one currency, such as $12.34.

    Amounts are stored as Decimal, never float, and rounded to whole cents
    with ROUND_HALF_EVEN. Money is immutable: it never changes after creation.
    """

    def __init__(self, amount: Decimal | int, currency: str = "USD") -> None:
        """Create Money from an exact amount, rounded to whole cents."""
        if isinstance(amount, bool) or not isinstance(amount, Decimal | int):
            raise TypeError(f"expected Decimal or int, got {type(amount).__name__}")
        if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
            raise ValueError(f"currency must be a code such as 'USD', not {currency!r}")

        value = Decimal(amount)
        if not value.is_finite():
            raise InvalidAmountError("An amount must be a finite number.")
        try:
            self._amount = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
        except InvalidOperation as err:
            raise InvalidAmountError("That amount is too large.") from err
        self._currency = currency

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Return an amount of nothing, such as $0.00."""
        return cls(0, currency)

    @classmethod
    def from_str(cls, text: str, currency: str = "USD") -> "Money":
        """Parse an amount typed by the user, such as '12.34' or '-5'.

        Raises InvalidAmountError if the text is not a number or has
        fractions of a cent. User input is never rounded.
        """
        try:
            value = Decimal(text)
        except InvalidOperation as err:
            raise InvalidAmountError(f"'{text}' is not a valid amount.") from err
        money = cls(value, currency)
        if money.amount != value:
            raise InvalidAmountError(f"'{text}' has fractions of a cent.")
        return money

    @property
    def amount(self) -> Decimal:
        """The amount, rounded to whole cents."""
        return self._amount

    @property
    def currency(self) -> str:
        """The three-letter currency code, such as 'USD'."""
        return self._currency

    def __str__(self) -> str:
        """Format for the user, such as '$1,234.56' or '-$54.20'."""
        sign = "-" if self._amount < 0 else ""
        symbol = "$" if self._currency == "USD" else f"{self._currency} "
        return f"{sign}{symbol}{abs(self._amount):,.2f}"

    def __repr__(self) -> str:
        """Show how to recreate this value: Money(Decimal('12.34'), 'USD')."""
        return f"Money({self._amount!r}, {self._currency!r})"

    def __eq__(self, other: object) -> bool:
        """Equal when both are Money with the same amount and currency."""
        if not isinstance(other, Money):
            return NotImplemented
        return self._amount == other._amount and self._currency == other._currency

    def __hash__(self) -> int:
        """Hash to match ==, so equal Money values work in sets and as keys."""
        return hash((self._amount, self._currency))

    def __lt__(self, other: object) -> bool:
        """Less than another Money in the same currency."""
        if not isinstance(other, Money):
            return NotImplemented
        self._requires_same_currency(other)
        return self._amount < other._amount

    def __bool__(self) -> bool:
        """False for zero and True otherwise, like a number."""
        return self._amount != 0

    def __add__(self, other: object) -> "Money":
        """Add another Money in the same currency."""
        if not isinstance(other, Money):
            return NotImplemented
        self._requires_same_currency(other)
        return self._with_amount(self._amount + other._amount)

    def __sub__(self, other: object) -> "Money":
        """Subtract another Money in the same currency."""
        if not isinstance(other, Money):
            return NotImplemented
        self._requires_same_currency(other)
        return self._with_amount(self._amount - other._amount)

    def __neg__(self) -> "Money":
        """Return the same amount with the opposite sign."""
        return self._with_amount(-self._amount)

    def __abs__(self) -> "Money":
        """Return the amount without its sign."""
        return self._with_amount(abs(self._amount))

    def __mul__(self, factor: object) -> "Money":
        """Scale by a whole number or Decimal, rounding to whole cents."""
        if isinstance(factor, bool) or not isinstance(factor, Decimal | int):
            return NotImplemented
        return self._with_amount(self._amount * factor)

    __rmul__ = __mul__

    def _with_amount(self, amount: Decimal) -> "Money":
        """Return a new Money in this currency with the given amount."""
        return Money(amount, self._currency)

    def _requires_same_currency(self, other: "Money") -> None:
        """Raise CurrencyMismatchError unless other has the same currency."""
        if self._currency != other._currency:
            raise CurrencyMismatchError(
                f"Cannot compare or combine {self._currency} and {other._currency}."
            )
