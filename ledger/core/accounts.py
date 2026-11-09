"""Accounts: the abstract base class and the three account types."""

from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from ledger.core.categories import Category
from ledger.core.decorators import logged, requires_positive_amount
from ledger.core.exceptions import (
    CreditLimitExceededError,
    InsufficientFundsError,
    LedgerError,
    ValidationError,
)
from ledger.core.mixins import InterestMixin, OverdraftMixin
from ledger.core.money import Money
from ledger.core.transaction import Transaction, TransactionKind


class Account(ABC):
    """State and behavior shared by every kind of account.

    Account is abstract: only its subclasses can be created, and each one
    must define minimum_balance, the lowest balance it allows. Each account
    type also sets TYPE, the name saved in the data file, such as "checking".
    """

    def __init__(
        self, name: str, opened_on: date, account_id: UUID | None = None
    ) -> None:
        """Create an account; a saved account passes its existing id."""
        self.name = name
        self.opened_on = opened_on
        self.id = account_id if account_id is not None else uuid4()
        self._transactions = []

    @property
    def name(self) -> str:
        """The name shown to the user, such as 'Everyday Checking'."""
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        """Rename the account; surrounding spaces are trimmed."""
        cleaned = value.strip()
        if not cleaned:
            raise ValidationError("An account name cannot be blank.")
        self._name = cleaned

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        """Every recorded transaction, oldest first, as a read-only tuple."""
        return tuple(self._transactions)

    @property
    def balance(self) -> Money:
        """The current balance: the sum of every recorded amount.

        It is worked out each time it is read and never stored, so it can
        never disagree with the history.
        """
        return sum((t.amount for t in self._transactions), Money.zero())

    def balance_on(self, day: date) -> Money:
        """The balance at the end of day: the sum of amounts dated on or before it.

        Transactions may be recorded out of date order (a CSV import or a
        backdated entry), so each one is checked by its date, not its position.
        """
        return sum(
            (t.amount for t in self._transactions if t.date <= day), Money.zero()
        )

    @logged
    @requires_positive_amount
    def deposit(
        self, amount: Money, on: date, category: Category, description: str
    ) -> Transaction:
        """Add money to the account and return the recorded transaction."""
        transaction = Transaction(
            date=on,
            amount=amount,
            kind=TransactionKind.DEPOSIT,
            category=category,
            description=description,
        )
        self._record(transaction)
        return transaction

    @logged
    @requires_positive_amount
    def withdraw(
        self, amount: Money, on: date, category: Category, description: str
    ) -> Transaction:
        """Take money out of the account and return the recorded transaction.

        Every account type uses this same method; only minimum_balance and the
        refusal error from _refusal() differ. If the withdrawal would go below
        the minimum, nothing is recorded.
        """
        self._check_withdrawal(amount)
        transaction = Transaction(
            date=on,
            amount=-amount,
            kind=TransactionKind.WITHDRAWAL,
            category=category,
            description=description,
        )
        self._record(transaction)
        return transaction

    def _check_withdrawal(self, amount: Money) -> None:
        """Raise the refusal error if taking amount out would break the minimum.

        Nothing is recorded, so a transfer can check its withdrawal before it
        records either half.
        """
        if self.balance - amount < self.minimum_balance:
            raise self._refusal(amount)

    def _refusal(self, amount: Money) -> LedgerError:
        """Build the error withdraw() raises when the minimum would be broken.

        This is a hook: an account type may override it to report the refusal
        its own way.
        """
        return InsufficientFundsError(
            f"Withdrawal of {amount} would take {self.name} below its "
            f"{self.minimum_balance} minimum."
        )

    def _record(self, transaction: Transaction) -> None:
        """Add a transaction to the end of the history.

        Only Ledger's own code calls this, after every check has passed.
        """
        self._transactions.append(transaction)

    def to_dict(self) -> dict:
        """Turn the account into JSON-safe values, its history included.

        "type" tells account_from_dict() which class to rebuild. Mixins and
        account types add their own fields through super().
        """
        return {
            "type": self.TYPE,
            "id": str(self.id),
            "name": self.name,
            "opened_on": self.opened_on.isoformat(),
            "transactions": [t.to_dict() for t in self._transactions],
        }

    @property
    @abstractmethod
    def minimum_balance(self) -> Money:
        """The lowest balance this account may reach."""


class CheckingAccount(OverdraftMixin, Account):
    """An everyday account with an optional overdraft (see OverdraftMixin)."""

    TYPE = "checking"


class SavingsAccount(InterestMixin, Account):
    """A savings account with an interest rate (see InterestMixin)."""

    TYPE = "savings"

    @property
    def minimum_balance(self) -> Money:
        """A savings account may not go below $0.00."""
        return Money.zero()

    def _interest_applies(self, balance: Money) -> bool:
        """Savings earns interest only on a positive balance."""
        return balance > Money.zero()


class CreditCardAccount(InterestMixin, Account):
    """A credit card: charges take the balance below $0.00, which is money owed.

    The balance may go down to minus the credit limit. Interest is charged on a
    negative balance (see InterestMixin).
    """

    TYPE = "credit_card"

    def __init__(self, *args, credit_limit: Money, **kwargs) -> None:
        """Keep credit_limit; pass every other argument along the MRO."""
        super().__init__(*args, **kwargs)
        self.credit_limit = credit_limit

    @property
    def credit_limit(self) -> Money:
        """The most that may be owed on this card, such as $2,000.00."""
        return self._credit_limit

    @credit_limit.setter
    def credit_limit(self, value: Money) -> None:
        """Change the limit; it must be Money more than $0.00."""
        if not isinstance(value, Money) or value <= Money.zero():
            raise ValidationError(
                f"A credit limit must be more than $0.00, not {value}."
            )
        self._credit_limit = value

    @property
    def minimum_balance(self) -> Money:
        """Minus the credit limit: the card may be owed up to its limit."""
        return -self.credit_limit

    def _interest_applies(self, balance: Money) -> bool:
        """A card charges interest only on money owed (a negative balance)."""
        return balance < Money.zero()

    def _refusal(self, amount: Money) -> LedgerError:
        """A charge past the limit is reported as CreditLimitExceededError."""
        return CreditLimitExceededError(
            f"A charge of {amount} would take {self.name} past its "
            f"{self.credit_limit} credit limit."
        )

    def to_dict(self) -> dict:
        """Add the credit limit, as exact text, to the fields saved by the MRO."""
        data = super().to_dict()
        data["credit_limit"] = str(self.credit_limit.amount)
        return data


def account_from_dict(data: dict) -> Account:
    """Rebuild an account saved by to_dict(), as the class its "type" names.

    The history is re-recorded with _record(), not deposit() or withdraw():
    each entry passed its checks when it was made, and an old balance may now
    sit below today's minimum. An unknown type raises ValueError.
    """
    name = data["name"]
    opened_on = date.fromisoformat(data["opened_on"])
    account_id = UUID(data["id"])
    account_type = data["type"]

    if account_type == CheckingAccount.TYPE:
        account = CheckingAccount(
            name,
            opened_on,
            account_id,
            overdraft_enabled=data["overdraft_enabled"],
        )
    elif account_type == SavingsAccount.TYPE:
        account = SavingsAccount(
            name,
            opened_on,
            account_id,
            interest_rate=Decimal(data["interest_rate"]),
            last_interest_date=date.fromisoformat(data["last_interest_date"]),
        )
    elif account_type == CreditCardAccount.TYPE:
        account = CreditCardAccount(
            name,
            opened_on,
            account_id,
            credit_limit=Money.from_str(data["credit_limit"]),
            interest_rate=Decimal(data["interest_rate"]),
            last_interest_date=date.fromisoformat(data["last_interest_date"]),
        )
    else:
        raise ValueError(f"Unknown account type: {account_type!r}")

    for saved in data["transactions"]:
        account._record(Transaction.from_dict(saved))
    return account
