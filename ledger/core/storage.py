"""Storage: save the book to a JSON file and load it back."""

import json
from pathlib import Path

from ledger.core.book import Book
from ledger.core.exceptions import LedgerError, StorageError

# The file both front ends use: a Ledger folder in the user's home folder,
# such as C:\Users\aaron\Ledger\ledger.json.
DATA_PATH = Path.home() / "Ledger" / "ledger.json"


def save_book(book: Book, path: Path = DATA_PATH) -> None:
    """Write the book to path as JSON, creating its folder if needed.

    A file system error raises StorageError.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(book.to_dict(), file, indent=2)
    except OSError as err:
        raise StorageError(f"Ledger could not save your data to {path}.") from err


def load_book(path: Path = DATA_PATH) -> Book:
    """Read the book from path.

    If there is no file yet (the first time Ledger runs), an empty book is
    returned. A file that can't be read, or whose contents can't be turned
    back into a book, raises StorageError.
    """
    if not path.exists():
        return Book()
    try:
        with path.open(encoding="utf-8") as file:
            return Book.from_dict(json.load(file))
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ArithmeticError,
        LedgerError,
    ) as err:
        raise StorageError(f"{path} is damaged and could not be loaded.") from err
