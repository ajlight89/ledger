# Ledger

Ledger is an offline personal finance tracker written in Python as a project
for an object-oriented programming course. It tracks checking, savings and
credit card accounts, records deposits, withdrawals and transfers, imports
transactions from bank CSV files, shows monthly statements and spending by
category, and saves everything to a local JSON file.

## Requirements

Python 3.12 or later. Ledger uses only the standard library.

## Running Ledger

From the project folder:

    python -m ledger        # graphical window
    python -m ledger.cli    # text menu
    python -m unittest      # automated tests

If Windows does not recognize `python`, use `py` instead (for example
`py -m ledger`).

Both front ends share one data file, `Ledger/ledger.json` in the user's home
folder, with an activity log, `ledger.log`, beside it.

## Building the Windows programs

With PyInstaller installed (`python -m pip install pyinstaller`), run from
the project folder:

    pyinstaller --onefile --windowed --name Ledger --paths . ledger\__main__.py
    pyinstaller --onefile --name LedgerCLI --paths . ledger\cli.py

`Ledger.exe` and `LedgerCLI.exe` are written to `dist/`.

## Project layout

- `ledger/core/` holds the core classes: Money, transactions, accounts, the
  Book, storage, reports and CSV import. The core never prints, asks for
  input or imports tkinter.
- `ledger/cli.py` is the text menu.
- `ledger/gui/` holds the tkinter window.
- `tests/` holds the automated tests for the core, the menu and the window,
  plus a manual checklist for the window (`gui_checklist.md`).
- `sample.csv` holds fake transactions for trying the CSV import.
