"""Mixins: small classes that each add one feature to an account type."""

import calendar
from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal

from ledger.core.categories import Category
from ledger.core.exceptions import ValidationError
from ledger.core.money import Money
from ledger.core.transaction import Transaction, TransactionKind


class OverdraftMixin:
    """Adds an overdraft toggle to an account type.

    While overdraft is on, the balance may go down to OVERDRAFT_FLOOR; while
    it is off, the balance may not go below $0.00. List this mixin before
    Account in the class line, so its methods come first in the MRO.
    """

    # The lowest balance allowed while overdraft is on.
    OVERDRAFT_FLOOR = Money.from_str("-500.00")

    def __init__(self, *args, overdraft_enabled: bool = False, **kwargs) -> None:
        """Keep overdraft_enabled; pass every other argument along the MRO."""
        super().__init__(*args, **kwargs)
        self.overdraft_enabled = overdraft_enabled

    @property
    def overdraft_enabled(self) -> bool:
        """Whether the balance may go below $0.00, down to OVERDRAFT_FLOOR."""
        return self._overdraft_enabled

    @overdraft_enabled.setter
    def overdraft_enabled(self, value: bool) -> None:
        """Turn overdraft on or off; only True or False is accepted."""
        if not isinstance(value, bool):
            raise ValidationError(
                f"Overdraft must be turned on or off (True or False), not {value!r}."
            )
        self._overdraft_enabled = value

    @property
    def minimum_balance(self) -> Money:
        """The overdraft floor while overdraft is on, otherwise $0.00."""
        if self.overdraft_enabled:
            return self.OVERDRAFT_FLOOR
        return Money.zero()

    def to_dict(self) -> dict:
        """Add overdraft_enabled to the fields saved by the rest of the MRO."""
        data = super().to_dict()
        data["overdraft_enabled"] = self.overdraft_enabled
        return data


class InterestMixin(ABC):
    """Adds an annual interest rate and monthly interest to an account type.

    The rate is a percentage, such as Decimal("4.5") for 4.5% a year. Each
    account type must define _interest_applies(), the hook that decides
    whether a balance earns or is charged interest. List this mixin before
    Account in the class line, so its methods come first in the MRO.
    """

    def __init__(
        self,
        *args,
        interest_rate: Decimal = Decimal("0"),
        last_interest_date: date | None = None,
        **kwargs,
    ) -> None:
        """Keep interest_rate and last_interest_date; pass the rest along the MRO.

        last_interest_date is the last day interest was posted for. A new account
        starts from its opening date; a saved account passes its own date.
        """
        super().__init__(*args, **kwargs)
        self.interest_rate = interest_rate
        self.last_interest_date = (
            last_interest_date if last_interest_date is not None else self.opened_on
        )

    @property
    def interest_rate(self) -> Decimal:
        """The annual interest rate as a percentage, from 0 to 100."""
        return self._interest_rate

    @interest_rate.setter
    def interest_rate(self, value: Decimal) -> None:
        """Change the rate; it must be a Decimal from 0 to 100."""
        if (
            not isinstance(value, Decimal)
            or not value.is_finite()
            or not 0 <= value <= 100
        ):
            raise ValidationError(
                f"The interest rate must be a percentage from 0 to 100, not {value}."
            )
        self._interest_rate = value

    def interest_for(self, balance: Money) -> Money:
        """One month of interest on balance, rounded to whole cents.

        The amount is balance x rate / 100 / 12. It is $0.00 when the hook says
        no interest applies to this balance.
        """
        if not self._interest_applies(balance):
            return Money.zero()
        return balance * (self.interest_rate / 100 / 12)

    def to_dict(self) -> dict:
        """Add the rate as exact text and last_interest_date as ISO text."""
        data = super().to_dict()
        data["interest_rate"] = str(self.interest_rate)
        data["last_interest_date"] = self.last_interest_date.isoformat()
        return data

    def accrue_interest(self, as_of: date) -> list[Transaction]:
        """Post interest for each month-end after last_interest_date, through as_of.

        Each month uses the balance on its month-end, so interest posted for one
        month earns (or is charged) interest the next. A month with $0.00 interest
        records nothing but still counts as done. Returns what was recorded.
        """
        posted = []
        for month_end in month_ends(self.last_interest_date, as_of):
            interest = self.interest_for(self.balance_on(month_end))
            if interest:
                transaction = Transaction(
                    date=month_end,
                    amount=interest,
                    kind=TransactionKind.INTEREST,
                    category=Category.INTEREST,
                    description="Interest",
                )
                self._record(transaction)
                posted.append(transaction)
            self.last_interest_date = month_end
        return posted

    @abstractmethod
    def _interest_applies(self, balance: Money) -> bool:
        """Whether interest applies to this balance; each account type decides."""


def month_ends(after: date, through: date) -> list[date]:
    """Every month-end later than after, up to and including through, in order.

    These are the days interest is posted. A month-end equal to after is left
    out, because its interest has already been posted.
    """
    ends = []
    year, month = after.year, after.month
    while True:
        last_day = calendar.monthrange(year, month)[1]
        month_end = date(year, month, last_day)
        if month_end > through:
            return ends
        if month_end > after:
            ends.append(month_end)
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
