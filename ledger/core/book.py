"""Book: the one object the front ends talk to. It owns every account."""

from datetime import date
from uuid import UUID, uuid4

from ledger.core.accounts import Account, account_from_dict
from ledger.core.categories import Category
from ledger.core.decorators import logged, requires_positive_amount
from ledger.core.exceptions import (
    AccountNotFoundError,
    DuplicateAccountError,
    ValidationError,
)
from ledger.core.mixins import InterestMixin
from ledger.core.money import Money
from ledger.core.transaction import Transaction, TransactionKind


class Book:
    """Every account the user has, and the actions that involve them.

    Book is a facade: the front ends call methods on Book and never need to know
    how accounts, transfers, interest or storage work inside.
    """

    def __init__(self) -> None:
        """Start an empty book."""
        # Accounts by id; a dict keeps the order they were added in.
        self._accounts = {}

    @property
    def accounts(self) -> tuple[Account, ...]:
        """Every account, in the order it was added, as a read-only tuple."""
        return tuple(self._accounts.values())

    @logged
    def add_account(self, account: Account) -> Account:
        """Add an account to the book and return it.

        Names must be unique, ignoring case. If another account already uses
        the name, DuplicateAccountError is raised and nothing is added.
        """
        existing = self._find_by_name(account.name)
        if existing is not None:
            raise self._duplicate_name_error(existing)
        self._accounts[account.id] = account
        return account

    def get_account(self, account_id: UUID) -> Account:
        """Return the account with this id; AccountNotFoundError if none."""
        try:
            return self._accounts[account_id]
        except KeyError as err:
            raise AccountNotFoundError("That account could not be found.") from err

    @logged
    def rename_account(self, account_id: UUID, new_name: str) -> Account:
        """Rename an account and return it.

        The new name must not be used by another account, ignoring case, but
        an account may change the case of its own name. Blank names are refused
        by the account's name property. If the rename is refused, the old name
        is kept.
        """
        account = self.get_account(account_id)
        existing = self._find_by_name(new_name.strip())
        if existing is not None and existing is not account:
            raise self._duplicate_name_error(existing)
        account.name = new_name
        return account

    @logged
    @requires_positive_amount
    def transfer(
        self,
        amount: Money,
        from_id: UUID,
        to_id: UUID,
        on: date,
        description: str,
    ) -> tuple[Transaction, Transaction]:
        """Move money from one account to another and return both halves.

        The money leaving is a TRANSFER_OUT and the money arriving is a
        TRANSFER_IN; one shared transfer_id links the two. Returns (out, in).

        Everything is checked before anything is recorded, so a refused
        transfer changes neither account.
        """
        if from_id == to_id:
            raise ValidationError("A transfer needs two different accounts.")
        source = self.get_account(from_id)
        destination = self.get_account(to_id)
        source._check_withdrawal(amount)
        link = uuid4()
        money_out = Transaction(
            date=on,
            amount=-amount,
            kind=TransactionKind.TRANSFER_OUT,
            category=Category.TRANSFER,
            description=description,
            transfer_id=link,
        )
        money_in = Transaction(
            date=on,
            amount=amount,
            kind=TransactionKind.TRANSFER_IN,
            category=Category.TRANSFER,
            description=description,
            transfer_id=link,
        )
        source._record(money_out)
        destination._record(money_in)
        return money_out, money_in

    @logged
    def accrue_all_interest(self, as_of: date) -> list[Transaction]:
        """Post the interest due through as_of on every account that has interest.

        The front ends call this when the app opens, passing today's date. Accounts
        without interest are skipped. Returns every transaction recorded.
        """
        posted = []
        for account in self._accounts.values():
            if isinstance(account, InterestMixin):
                posted.extend(account.accrue_interest(as_of))
        return posted

    def to_dict(self) -> dict:
        """Turn the whole book into JSON-safe values."""
        return {"accounts": [a.to_dict() for a in self._accounts.values()]}

    @classmethod
    def from_dict(cls, data: dict) -> "Book":
        """Rebuild a book saved by to_dict().

        Accounts go through add_account(), so two with one name are refused
        just as they would be in the app.
        """
        book = cls()
        for saved in data["accounts"]:
            book.add_account(account_from_dict(saved))
        return book

    def _find_by_name(self, name: str) -> Account | None:
        """Return the account with this name, ignoring case, or None if none."""
        wanted = name.casefold()
        for account in self._accounts.values():
            if account.name.casefold() == wanted:
                return account
        return None

    def _duplicate_name_error(self, existing: Account) -> DuplicateAccountError:
        """Build the error raised when a name is already used by existing."""
        return DuplicateAccountError(
            f"An account named {existing.name} already exists."
        )
