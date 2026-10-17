# Ledger

An offline personal finance tracker for Windows, written in Python.

Ledger lets you manage your personal finances on your own computer. You can create checking, savings and credit card accounts, record deposits, withdrawals and transfers, import transactions from a bank's CSV export, and view monthly statements and spending by category. All data is stored locally as JSON files, so Ledger needs no server, account or internet connection, and your data can't be lost to a service shutting down.

Ledger is the final project for CPTR212 Object Oriented Programming (fall 2026). Its code is organized to demonstrate the course's object-oriented programming topics.

**Status:** in development (v0.1.0).

## Features

_Planned: a short list of what Ledger can do._

## Screenshots

_Planned: the main window, a monthly statement and the CSV import summary._

## Download and run

_Planned: how to download `Ledger.exe` from the v1.0.0 Release and run it, including a note on the Windows SmartScreen warning._

## Run from source

_Planned: how to clone the repository, install it and launch the app with `python -m ledger`._

## Run the tests

_Planned: how to run the `unittest` suite._

## Build the Windows executable

_Planned: how to build `Ledger.exe` with PyInstaller._

## Project structure

_Planned: what each package and module is responsible for._

## Class diagram

Classes are added here as they are built. Solid arrows with hollow heads show inheritance; dashed arrows show which errors a class raises. Members marked `#` are protected by convention.

```mermaid
classDiagram
    %% #95; is an underscore. Writing dunder names with it stops Mermaid
    %% reading double underscores as bold text and dropping them.
    class Money {
        #Decimal _amount
        #str _currency
        +Decimal amount
        +str currency
        +#95;#95;init#95;#95;(amount, currency)
        +#95;#95;repr#95;#95;() str
        +#95;#95;str#95;#95;() str
        +#95;#95;eq#95;#95;(other) bool
        +#95;#95;hash#95;#95;() int
        +#95;#95;add#95;#95;(other) Money
        +#95;#95;sub#95;#95;(other) Money
        +#95;#95;neg#95;#95;() Money
        +#95;#95;mul#95;#95;(factor) Money
        +#95;#95;rmul#95;#95;(factor) Money
        +#95;#95;lt#95;#95;(other) bool
    }
    note for Money "Immutable value object: amount and currency are read-only properties.<br>Amounts are Decimal, rounded half up to cents; floats are rejected.<br>total_ordering derives the other comparisons from lt and eq."

    class Exception
    class LedgerError
    class InvalidAmountError
    class InvalidCurrencyError
    class CurrencyMismatchError {
        +str left
        +str right
        +#95;#95;init#95;#95;(left, right)
    }

    Exception <|-- LedgerError
    LedgerError <|-- InvalidAmountError
    LedgerError <|-- InvalidCurrencyError
    LedgerError <|-- CurrencyMismatchError

    Money ..> InvalidAmountError : raises
    Money ..> InvalidCurrencyError : raises
    Money ..> CurrencyMismatchError : raises
```

## Design notes

_Planned: the key design decisions, such as storing money as `Decimal`, the credit card sign convention, all-or-nothing transfers, atomic saves and where data is stored._

## Known limitations

_Planned: what Ledger does not do._

## License

MIT. See [LICENSE](LICENSE).
