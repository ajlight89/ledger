"""CSV import: add the rows of a bank's exported CSV file to an account."""

import csv
from datetime import datetime
from pathlib import Path

from ledger.core.accounts import Account
from ledger.core.categories import Category
from ledger.core.decorators import logged
from ledger.core.exceptions import CsvFormatError, LedgerError
from ledger.core.money import Money
from ledger.core.transaction import Transaction, TransactionKind

# The columns every file must have, and how its dates are written: 10/03/2026.
COLUMNS = ("Date", "Description", "Amount")
DATE_FORMAT = "%m/%d/%Y"

# Words that pick the category of money paid out, if found in a description.
KEYWORDS = {
    Category.HOUSING: ["rent", "mortgage", "hotel"],
    Category.UTILITIES: ["electric", "water", "sewer", "internet", "heating", "gas"],
    Category.FOOD_GROCERIES: ["grocery"],
    Category.DINING_OUT: ["pizza", "restaurant", "grubhub", "uber eats", "cafe"],
    Category.TRANSPORTATION: ["fuel", "airfare", "subway token", "bus"],
    Category.SUBSCRIPTIONS: ["subscription"],
    Category.SHOPPING: ["amazon", "wal-mart", "costco", "store"],
    Category.INSURANCE: ["insurance"],
    Category.ENTERTAINMENT: ["movie", "bowling", "entertainment"],
    Category.DEBT_PAYMENT: [
        "interest payment",
        "credit card payment",
        "payment on account",
    ],
}


def guess_category(description: str) -> Category:
    """Pick the category whose word is in the description, or Other if none.

    Only whole words match: spaces are added around the description and
    around each word, so "bus" matches "CITY BUS" but not "BUSINESS".
    """
    text = f" {description.casefold()} "
    for category, words in KEYWORDS.items():
        for word in words:
            if f" {word} " in text:
                return category
    return Category.OTHER


def parse_row(row: dict) -> Transaction:
    """Turn one CSV row into a deposit (money in) or a withdrawal (money out).

    A bad date raises CsvFormatError; a bad amount or blank description
    raises the LedgerError that Money or Transaction reports.
    """
    text = row["Date"].strip()
    try:
        day = datetime.strptime(text, DATE_FORMAT).date()
    except ValueError as err:
        raise CsvFormatError(f"'{text}' is not a date like 10/03/2026.") from err
    amount = Money.from_str(row["Amount"].strip())
    description = row["Description"].strip()
    if amount.amount > 0:
        kind, category = TransactionKind.DEPOSIT, Category.INCOME
    else:
        kind, category = TransactionKind.WITHDRAWAL, guess_category(description)
    return Transaction(day, amount, kind, category, description)


@logged
def import_csv(account: Account, path: Path) -> list[Transaction]:
    """Add every new row of a bank CSV file to account; return what was added.

    Every row is read and checked before any is added, so a bad row adds
    nothing. A row with the same date, amount and description as a
    transaction already in the account is skipped, so importing the same
    file twice adds nothing the second time.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file, restval="")
            if reader.fieldnames is None or not set(COLUMNS) <= set(reader.fieldnames):
                raise CsvFormatError(
                    f"{path} needs the columns Date, Description and Amount."
                )
            rows = []
            for row in reader:
                try:
                    rows.append(parse_row(row))
                except LedgerError as err:
                    raise CsvFormatError(
                        f"Line {reader.line_num} of {path}: {err}"
                    ) from err
    except OSError as err:
        raise CsvFormatError(f"{path} could not be opened.") from err

    existing = {(t.date, t.amount, t.description) for t in account.transactions}
    added = []
    for transaction in rows:
        key = (transaction.date, transaction.amount, transaction.description)
        if key not in existing:
            account._record(transaction)
            added.append(transaction)
    return added
