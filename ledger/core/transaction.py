"""Transactions: single entries that move money into or out of an account."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum, unique
from uuid import UUID, uuid4

from ledger.core.categories import Category
from ledger.core.exceptions import InvalidAmountError, ValidationError
from ledger.core.money import Money


@unique
class TransactionKind(Enum):
    """How money moved; each value is the label shown to the user."""

    DEPOSIT = "Deposit"
    WITHDRAWAL = "Withdrawal"
    TRANSFER_IN = "Transfer In"
    TRANSFER_OUT = "Transfer Out"
    INTEREST = "Interest"

    def __str__(self) -> str:
        """Return the label shown to the user, such as 'Transfer In'."""
        return self.value


# Money in must be positive and money out negative. INTEREST may be either:
# earned on savings (in) or charged on a credit card (out).
_MONEY_IN = frozenset({TransactionKind.DEPOSIT, TransactionKind.TRANSFER_IN})
_MONEY_OUT = frozenset({TransactionKind.WITHDRAWAL, TransactionKind.TRANSFER_OUT})
_TRANSFERS = frozenset({TransactionKind.TRANSFER_IN, TransactionKind.TRANSFER_OUT})


@dataclass(frozen=True)
class Transaction:
    """One entry in an account's history.

    A positive amount is money in; a negative amount is money out.
    Transactions are frozen: once recorded, they never change.
    """

    date: date
    amount: Money
    kind: TransactionKind
    category: Category
    description: str
    id: UUID = field(default_factory=uuid4)
    transfer_id: UUID | None = None

    def __post_init__(self) -> None:
        """Check the rules every transaction must follow when it is created."""
        if not self.amount:
            raise InvalidAmountError("A transaction amount cannot be $0.00.")
        if not self.description.strip():
            raise ValidationError("A transaction needs a description.")
        # These rules can only be broken by a bug in Ledger's own code,
        # so they raise ValueError rather than a LedgerError for the user.
        if self.kind in _MONEY_IN and self.amount.amount < 0:
            raise ValueError(f"A {self.kind} must be positive, not {self.amount}.")
        if self.kind in _MONEY_OUT and self.amount.amount > 0:
            raise ValueError(f"A {self.kind} must be negative, not {self.amount}.")
        is_transfer = self.kind in _TRANSFERS
        if is_transfer and self.transfer_id is None:
            raise ValueError(f"A {self.kind} must have a transfer_id.")
        if not is_transfer and self.transfer_id is not None:
            raise ValueError(f"A {self.kind} cannot have a transfer_id.")

    def to_dict(self) -> dict[str, str | None]:
        """Turn the transaction into JSON-safe values: text, or None.

        Money is saved as exact text such as "-54.20", the date as ISO text such
        as "2026-10-03", the kind and category by name, and the ids as text.
        """
        return {
            "id": str(self.id),
            "date": self.date.isoformat(),
            "amount": str(self.amount.amount),
            "kind": self.kind.name,
            "category": self.category.name,
            "description": self.description,
            "transfer_id": None if self.transfer_id is None else str(self.transfer_id),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        """Rebuild a transaction saved by to_dict().

        The rules in __post_init__ run again, so damaged data is refused. A
        missing key or unknown name raises KeyError; a badly formed value raises
        ValueError or a LedgerError such as InvalidAmountError.
        """
        transfer_id = data["transfer_id"]
        return cls(
            date=date.fromisoformat(data["date"]),
            amount=Money.from_str(data["amount"]),
            kind=TransactionKind[data["kind"]],
            category=Category[data["category"]],
            description=data["description"],
            id=UUID(data["id"]),
            transfer_id=None if transfer_id is None else UUID(transfer_id),
        )
