# Ledger

Ledger is an offline personal finance tracker written in Python as a project
for an object-oriented programming course. It tracks checking, savings and
credit card accounts, records deposits, withdrawals and transfers, and saves
everything to a local JSON file.

## Requirements

Python 3.12 or later. Ledger uses only the standard library.

## Running the tests

From the project folder:

    python -m unittest

## Project layout

- `ledger/core/` holds the core classes: Money, transactions, accounts, the
  Book and storage. The core never prints, asks for input or imports tkinter.
- `tests/` holds the unit tests for the core.
