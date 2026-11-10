"""Text menu for Ledger.

Run from the project folder with: python -m ledger.cli
Every action runs inside one try/except, so a refused action (a LedgerError)
prints its message and the menu keeps going.
"""

import logging
from datetime import date

from ledger.core import storage
from ledger.core.book import Book
from ledger.core.exceptions import LedgerError

LOG_PATH = storage.DATA_PATH.parent / "ledger.log"


def list_accounts(book: Book) -> None:
    """Print each account with a number, its type and its balance."""
    if not book.accounts:
        print("No accounts yet.")
        return
    for number, account in enumerate(book.accounts, start=1):
        print(f"{number}. {account.name} ({account.TYPE}): {account.balance}")


# Menu key -> (label shown in the menu, function that does the work).
# Every action function takes the book as its only argument.
ACTIONS = {
    "1": ("List accounts", list_accounts),
}


def show_menu() -> None:
    """Print the menu choices."""
    print()
    for key, (label, _action) in ACTIONS.items():
        print(f"{key}. {label}")
    print("Q. Quit")


def main() -> None:
    """Load the book, post any interest due, then run the menu until Quit."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        book = storage.load_book()
        if book.accrue_all_interest(date.today()):
            storage.save_book(book)
    except LedgerError as err:
        print(err)
        return

    print("*--- Ledger ---*")
    while True:
        show_menu()
        choice = input("Choose: ").strip().upper()
        if choice == "Q":
            break
        if choice not in ACTIONS:
            print("Please choose one of the numbers shown, or Q.")
            continue
        _label, action = ACTIONS[choice]
        try:
            action(book)
        except LedgerError as err:
            print(err)
    print("Goodbye.")


if __name__ == "__main__":
    main()
