"""Text menu for Ledger.

Run from the project folder with: python -m ledger.cli
Every action runs inside one try/except, so a refused action (a LedgerError)
prints its message and the menu keeps going.
"""

import logging
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ledger.core import importer, reports, storage
from ledger.core.accounts import (
    Account,
    CheckingAccount,
    CreditCardAccount,
    SavingsAccount,
)
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import (
    AccountNotFoundError,
    CreditLimitExceededError,
    DuplicateAccountError,
    InsufficientFundsError,
    InvalidAmountError,
    LedgerError,
    ValidationError,
)
from ledger.core.money import Money

LOG_PATH = storage.DATA_PATH.parent / "ledger.log"

# ANSI escape codes: bright green text, then back to the terminal's normal colors.
GREEN = "\033[92m"
RESET = "\033[0m"

BANNER = r"""
 _      _____ ____   ____ _____ ____
| |    | ____|  _ \ / ___| ____|  _ \
| |    |  _| | | | | |  _|  _| | |_) |
| |___ | |___| |_| | |_| | |___|  _ <
|_____||_____|____/ \____|_____|_| \_\

      Personal finance, kept offline.
"""

# Refusals about the amount itself; the user may try a different amount.
AMOUNT_ERRORS = (InvalidAmountError, InsufficientFundsError, CreditLimitExceededError)


# ----- Input helpers: each one asks again until the answer is usable. -----


def ask_text(prompt: str) -> str:
    """Ask until the user types something that isn't blank."""
    while True:
        text = input(prompt).strip()
        if text:
            return text
        print("Please type something.")


def ask_number(prompt: str, highest: int) -> int:
    """Ask until the user types a whole number from 1 to highest."""
    while True:
        text = input(prompt).strip()
        if text.isdigit() and 1 <= int(text) <= highest:
            return int(text)
        print(f"Please type a number from 1 to {highest}.")


def ask_yes_no(prompt: str) -> bool:
    """Ask until the user types y or n; return True for y."""
    while True:
        text = input(prompt).strip().lower()
        if text in ("y", "yes"):
            return True
        if text in ("n", "no"):
            return False
        print("Please type y or n.")


def ask_money(prompt: str) -> Money:
    """Ask until the user types an amount such as 12.34, $1,200 or 5."""
    while True:
        text = input(prompt).strip().replace("$", "").replace(",", "")
        try:
            return Money.from_str(text)
        except InvalidAmountError as err:
            print(err)


def ask_rate(prompt: str) -> Decimal:
    """Ask until the user types a number, such as 4.5 or 4.5 percent."""
    while True:
        text = input(prompt).strip().replace("%", "")
        try:
            return Decimal(text)
        except InvalidOperation:
            print(f"'{text}' is not a number.")


def ask_date(prompt: str) -> date:
    """Ask until the user types a date as MM/DD/YYYY; blank means today."""
    while True:
        text = input(prompt).strip()
        if not text:
            return date.today()
        try:
            return datetime.strptime(text, "%m/%d/%Y").date()
        except ValueError:
            print(f"'{text}' is not a date like 11/10/2026.")


def pick_from(accounts, prompt: str, empty_message: str) -> Account:
    """Number the accounts and return the one the user picks.

    accounts may be the active or the archived accounts. If there are none,
    AccountNotFoundError is raised with empty_message.
    """
    if not accounts:
        raise AccountNotFoundError(empty_message)
    show_numbered(accounts)
    number = ask_number(prompt, len(accounts))
    return accounts[number - 1]


def choose_account(book: Book, prompt: str = "Account number: ") -> Account:
    """List the active accounts and return the one the user picks by number."""
    return pick_from(
        book.accounts, prompt, "There are no accounts yet. Open one first."
    )


def choose_category() -> Category:
    """List the categories a user may pick and return the chosen one."""
    # Transfer and Interest are recorded by Ledger itself, never typed in.
    skip = (Category.TRANSFER, Category.INTEREST)
    choices = [c for c in Category if c not in skip]
    for number, category in enumerate(choices, start=1):
        print(f"{number}. {category}")
    return choices[ask_number("Category number: ", len(choices)) - 1]


def record_transaction(method) -> Money | None:
    """Ask for the details, then call method (account.deposit or .withdraw).

    If the account refuses the amount (zero or negative, not enough money, or
    over the credit limit), the user may try a different amount or give up.
    Returns the amount recorded, or None if the user gave up.
    """
    amount = ask_money("Amount: ")
    on = ask_date("Date (MM/DD/YYYY, blank for today): ")
    category = choose_category()
    description = ask_text("Description: ")
    while True:
        try:
            method(amount, on, category, description)
            return amount
        except AMOUNT_ERRORS as err:
            print(err)
            if not ask_yes_no("Try a different amount? (y/n): "):
                return None
            amount = ask_money("Amount: ")


def ask_month(prompt: str) -> tuple[int, int]:
    """Ask until the user types a month as MM/YYYY; blank means this month.

    Returns (year, month), such as (2026, 10).
    """
    while True:
        text = input(prompt).strip()
        if not text:
            today = date.today()
            return today.year, today.month
        try:
            day = datetime.strptime(text, "%m/%Y")
            return day.year, day.month
        except ValueError:
            print(f"'{text}' is not a month like 10/2026")


# ----- Menu actions: each takes the book as its only argument. -----


def show_numbered(accounts) -> None:
    """Print each account with a number, its type and its balance."""
    for number, account in enumerate(accounts, start=1):
        print(f"{number}. {account.name} ({account.TYPE}): {account.balance}")


def list_accounts(book: Book) -> None:
    """Print the active accounts, numbered."""
    if not book.accounts:
        print("No accounts yet.")
        return
    show_numbered(book.accounts)


def set_interest_rate(account) -> None:
    """Ask until the account's interest_rate property accepts the rate."""
    while True:
        try:
            account.interest_rate = ask_rate("Annual interest rate in percent: ")
            return
        except ValidationError as err:
            print(err)


def new_credit_card(name: str, opened_on: date) -> CreditCardAccount:
    """Ask until the credit_limit property accepts the limit; return the card."""
    while True:
        try:
            limit = ask_money("Credit limit: ")
            return CreditCardAccount(name, opened_on, credit_limit=limit)
        except ValidationError as err:
            print(err)


def add_with_unique_name(book: Book, account) -> None:
    """Add the account, asking for a new name until no other account uses it."""
    while True:
        try:
            book.add_account(account)
            return
        except DuplicateAccountError as err:
            print(err)
            account.name = ask_text("Account name: ")


def open_account(book: Book) -> None:
    """Ask for the account type and its details, then add it to the book."""
    print("1. Checking\n2. Savings\n3. Credit Card")
    kind = ask_number("Account type: ", 3)
    name = ask_text("Account name: ")
    today = date.today()
    if kind == 1:
        overdraft = ask_yes_no("Allow overdraft down to -$500? (y/n): ")
        account = CheckingAccount(name, today, overdraft_enabled=overdraft)
    elif kind == 2:
        account = SavingsAccount(name, today)
        set_interest_rate(account)
    else:
        account = new_credit_card(name, today)
        set_interest_rate(account)
    add_with_unique_name(book, account)
    storage.save_book(book)
    print(f"Opened {account.name}.")


def deposit(book: Book) -> None:
    """Add money to an account (on a credit card, a payment)."""
    account = choose_account(book)
    amount = record_transaction(account.deposit)
    if amount is None:
        print("Nothing was recorded.")
        return
    storage.save_book(book)
    print(f"Deposited {amount}. {account.name} balance: {account.balance}")


def withdraw(book: Book) -> None:
    """Take money out of an account (on a credit card, a charge)."""
    account = choose_account(book)
    amount = record_transaction(account.withdraw)
    if amount is None:
        print("Nothing was recorded.")
        return
    storage.save_book(book)
    print(f"Withdrew {amount}. {account.name} balance: {account.balance}")


def transfer(book: Book) -> None:
    """Move money between two accounts, such as paying a credit card."""
    if len(book.accounts) < 2:
        raise ValidationError("A transfer needs at least two accounts.")
    source = choose_account(book, "From account number: ")
    destination = choose_account(book, "To account number: ")
    amount = ask_money("Amount: ")
    on = ask_date("Date (MM/DD/YYYY, blank for today): ")
    description = ask_text("Description: ")
    while True:
        try:
            book.transfer(amount, source.id, destination.id, on, description)
            break
        except AMOUNT_ERRORS as err:
            print(err)
            if not ask_yes_no("Try a different amount? (y/n): "):
                print("Nothing was recorded.")
                return
            amount = ask_money("Amount: ")
    storage.save_book(book)
    print(f"Moved {amount} from {source.name} to {destination.name}.")


def rename_account(book: Book) -> None:
    """Give an account a new name, asking again if another account has it."""
    account = choose_account(book, "Account to rename: ")
    while True:
        try:
            book.rename_account(account.id, ask_text("New name: "))
            break
        except DuplicateAccountError as err:
            print(err)
    storage.save_book(book)
    print(f"Renamed to {account.name}.")


def archive_account(book: Book) -> None:
    """Move an account with a $0.00 balance to the archive, after a y/n check."""
    account = choose_account(book, "Account to archive: ")
    if not ask_yes_no(f"Archive {account.name}? It can be restored later. (y/n): "):
        print("Nothing was changed.")
        return
    book.archive_account(account.id)
    storage.save_book(book)
    print(f"Archived {account.name}.")


def restore_account(book: Book) -> None:
    """Bring an archived account back, offering a new name if its name is taken."""
    account = pick_from(
        book.archived_accounts,
        "Account to restore: ",
        "There are no archived accounts.",
    )
    original_name = account.name
    try:
        while True:
            try:
                book.restore_account(account.id)
                break
            except DuplicateAccountError as err:
                print(err)
                if not ask_yes_no("Restore it under a different name? (y/n): "):
                    account.name = original_name
                    print("The account stays archived.")
                    return
                account.name = ask_text("New name: ")
    except KeyboardInterrupt:
        account.name = original_name
        raise
    storage.save_book(book)
    print(f"Restored {account.name}.")


def import_transactions(book: Book) -> None:
    """Add the rows of a bank CSV file to an account."""
    account = choose_account(book, "Import into account number: ")
    # Windows "Copy as path" puts quotes around the path; remove them.
    path = Path(ask_text("CSV file path: ").strip('"'))
    added = importer.import_csv(account, path)
    if not added:
        print("No new transactions; every row was already in the account.")
        return
    storage.save_book(book)
    print(f"Imported {len(added)} transactions.")
    print(f"{account.name} balance: {account.balance}")


def show_statement(book: Book) -> None:
    """Print one account's transactions for a month with a running balance."""
    if book.archived_accounts and ask_yes_no(
        "Statement for an archived account? (y/n): "
    ):
        account = pick_from(
            book.archived_accounts,
            "Statement for archived account number: ",
            "There are no archived accounts.",
        )
    else:
        account = choose_account(book, "Statement for account number: ")
    year, month = ask_month("Month (MM/YYYY, blank for this month): ")
    opening = reports.opening_balance(account, year, month)
    print(f"\n{account.name}: {date(year, month, 1):%B %Y}")
    print(f"Opening balance: {opening}")
    print(f"{'Date':<10}  {'Description':<30}  {'Amount':>12}  {'Balance':>12}")
    closing = opening
    count = 0
    for line in reports.statement_lines(account, year, month):
        print(
            f"{line.date:%m/%d/%Y}  {line.description:<30.30}  "
            f"{line.amount!s:>12}  {line.balance!s:>12}"
        )
        closing = line.balance
        count += 1
    if count == 0:
        print("No transactions this month.")
    print(f"Closing balance: {closing}")


def show_spending(book: Book) -> None:
    """Print how much was spent in each category in a month, largest first."""
    year, month = ask_month("Month (MM/YYYY, blank for this month): ")
    totals = reports.spending_by_category(book, year, month)
    print(f"\nSpending for {date(year, month, 1):%B %Y}")
    if not totals:
        print("No spending this month.")
        return
    for category, amount in totals.items():
        print(f"{category!s:<20}  {amount!s:>12}")
    total = sum(totals.values(), Money.zero())
    print(f"{'Total':<20}  {total!s:>12}")


# Menu key -> (label shown in the menu, function that does the work).
# Every action function takes the book as its only argument.
ACTIONS = {
    "1": ("List accounts", list_accounts),
    "2": ("Open account", open_account),
    "3": ("Deposit", deposit),
    "4": ("Withdraw", withdraw),
    "5": ("Transfer", transfer),
    "6": ("Rename account", rename_account),
    "7": ("Archive account", archive_account),
    "8": ("Restore account", restore_account),
    "9": ("Import CSV file", import_transactions),
    "10": ("Monthly statement", show_statement),
    "11": ("Spending by category", show_spending),
}


def show_menu() -> None:
    """Print the menu choices."""
    print()
    for key, (label, _action) in ACTIONS.items():
        print(f"{key:>2}. {label}")
    print(" Q. Quit")
    print()
    print("Press Ctrl+C at any prompt to return to this menu.")
    print()


def setup_logging() -> None:
    """Send the core's log messages to ledger.log beside the data file."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> None:
    """Run the menu, in green when the output is a real terminal."""
    use_color = sys.stdout.isatty()
    if use_color:
        print(GREEN, end="")
    try:
        run_menu()
    finally:
        if use_color:
            print(RESET, end="")


def run_menu() -> None:
    """Load the book, post any interest due, then run the menu until Quit."""
    setup_logging()

    try:
        book = storage.load_book()
        if book.accrue_all_interest(date.today()):
            storage.save_book(book)
    except LedgerError as err:
        print(err)
        return

    print(BANNER)
    while True:
        show_menu()
        try:
            choice = input("Please select an option: ").strip().upper()
        except KeyboardInterrupt:
            print()
            break
        if choice == "Q":
            break
        if choice not in ACTIONS:
            print("Please choose one of the numbers shown, or Q.")
            continue
        label, action = ACTIONS[choice]
        print(f"Option {choice} selected: {label}  (Ctrl+C = back)")
        try:
            action(book)
        except LedgerError as err:
            print(err)
        except KeyboardInterrupt:
            print("\nBack to the main menu. Nothing was changed.")
    print("Goodbye.")


if __name__ == "__main__":
    main()
