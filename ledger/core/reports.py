"""Reports: monthly statements and spending by category."""

import calendar
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from ledger.core.accounts import Account
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import ValidationError
from ledger.core.money import Money


@dataclass(frozen=True)
class StatementLine:
    """One line of a monthly statement: a transaction and the balance after it."""

    date: date
    description: str
    amount: Money
    balance: Money


def month_range(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of the month, such as Oct 1 and Oct 31.

    A month outside 1 to 12 raises ValidationError.
    """
    if not 1 <= month <= 12:
        raise ValidationError(f"A month must be from 1 to 12, not {month}.")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def opening_balance(account: Account, year: int, month: int) -> Money:
    """The balance at the start of the month: the end of the day before it."""
    first, _ = month_range(year, month)
    return account.balance_on(first - timedelta(days=1))


def statement_lines(account: Account, year: int, month: int) -> Iterator[StatementLine]:
    """Yield one StatementLine per transaction in the month, oldest first.

    This is a generator: nothing runs until the caller asks for the first
    line, and each line is made only when it is asked for. The running
    balance starts from opening_balance().
    """
    first, last = month_range(year, month)
    balance = opening_balance(account, year, month)
    in_month = [t for t in account.transactions if first <= t.date <= last]
    for transaction in sorted(in_month, key=lambda t: t.date):
        balance = balance + transaction.amount
        yield StatementLine(
            transaction.date, transaction.description, transaction.amount, balance
        )


def spending_by_category(book: Book, year: int, month: int) -> dict[Category, Money]:
    """Total spending in each category for one month, across every account.

    Only money out (a negative amount) in a spending category counts, so
    income and transfers are left out. Totals are positive, largest first.
    """
    first, last = month_range(year, month)
    totals = {}
    for account in book.accounts:
        for t in account.transactions:
            is_money_out = t.amount.amount < 0
            if first <= t.date <= last and is_money_out and t.category.is_spending:
                totals[t.category] = totals.get(t.category, Money.zero()) + abs(
                    t.amount
                )
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))
