"""The fixed list of categories a transaction can be filed under."""

from enum import Enum, unique


@unique
class Category(Enum):
    """A transaction category; each value is the label shown to the user."""

    INCOME = "Income"
    HOUSING = "Housing"
    UTILITIES = "Utilities"
    FOOD_GROCERIES = "Food & Groceries"
    DINING_OUT = "Dining Out"
    TRANSPORTATION = "Transportation"
    HEALTHCARE = "Healthcare"
    INSURANCE = "Insurance"
    ENTERTAINMENT = "Entertainment"
    SHOPPING = "Shopping"
    SUBSCRIPTIONS = "Subscriptions"
    DEBT_PAYMENT = "Debt Payment"
    TRANSFER = "Transfer"
    INTEREST = "Interest"
    OTHER = "Other"

    def __str__(self) -> str:
        """Return the label shown to the user, such as 'Food & Groceries'."""
        return self.value

    @property
    def is_spending(self) -> bool:
        """Whether money paid out in this category counts as spending."""
        return self not in _NON_SPENDING


# Income, and transfers between the user's own accounts, are not spending.
# Interest counts only when it is paid out (charged on a credit card).
_NON_SPENDING = frozenset({Category.INCOME, Category.TRANSFER})
