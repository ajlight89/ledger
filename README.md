# Ledger

An offline personal finance tracker for Windows, written in Python.

Ledger lets you manage your personal finances on your own computer. You can create checking, savings and credit card accounts, record deposits, withdrawals and transfers, import transactions from a bank's CSV export, and view monthly statements and spending by category. All data is stored locally as JSON files, so Ledger needs no server, account or internet connection, and your data can't be lost to a service shutting down.

Ledger is my final project for CPTR212 Object Oriented Programming (Fall 2026). Its code is organized to demonstrate the course's object-oriented programming topics.

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

Classes are added here as they are built. Solid arrows with hollow heads show inheritance, a plain arrow shows that a class holds a value of another class, and dashed arrows show which errors a class raises. Members marked `#` are protected by convention, and methods in _italics_ are abstract.

### Accounts

```mermaid
classDiagram
    %% #95; is an underscore. Mermaid can read a pair of underscores on one
    %% line as bold or italic text and drop them, so dunder names, and any
    %% line with two or more underscores, use #95; for each underscore.
    class Account {
        <<abstract>>
        #str _name
        #Money _balance
        +str name
        +Money balance
        +str currency
        +str account_type
        +#95;#95;init#95;#95;(name, currency)
        +available_funds()* Money
        +deposit(amount) None
        +withdraw(amount) None
        ##95;check#95;amount(amount) None
        ##95;check#95;limit(limit, label) Money
        +#95;#95;repr#95;#95;() str
        +#95;#95;str#95;#95;() str
    }
    note for Account "Abstract: account#95;type (a property) and available#95;funds().<br>Balance is read-only; only deposit() and withdraw() change it.<br>Positive balance = money you have; negative = money you owe."

    class InterestMixin {
        <<mixin>>
        #Decimal #95;interest#95;rate
        +Decimal interest_rate
        +monthly_interest() Money
        +apply#95;monthly#95;interest() Money
    }

    class OverdraftProtectionMixin {
        <<mixin>>
        #Money #95;overdraft#95;limit
        +Money overdraft_limit
        +available_funds() Money
    }

    class CheckingAccount {
        +str account_type
        +#95;#95;init#95;#95;(name, overdraft_limit, currency)
    }
    note for CheckingAccount "Method resolution order: CheckingAccount,<br>OverdraftProtectionMixin, Account, so the<br>mixin's available_funds() is the one used."

    class SavingsAccount {
        +str account_type
        +#95;#95;init#95;#95;(name, interest_rate, currency)
        +available_funds() Money
    }

    class CreditCardAccount {
        #Money #95;credit#95;limit
        +str account_type
        +Money credit_limit
        +#95;#95;init#95;#95;(name, credit_limit, currency)
        +available_funds() Money
    }

    class Money

    Account <|-- CheckingAccount
    OverdraftProtectionMixin <|-- CheckingAccount
    Account <|-- SavingsAccount
    InterestMixin <|-- SavingsAccount
    Account <|-- CreditCardAccount
    Account --> Money : balance
```

### Money and errors

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

    class Account {
        <<abstract>>
    }

    class Exception
    class LedgerError
    class InvalidAmountError
    class InvalidCurrencyError
    class CurrencyMismatchError {
        +str left
        +str right
        +#95;#95;init#95;#95;(left, right)
    }
    class InvalidAccountSettingError
    class InsufficientFundsError {
        +Money requested
        +Money available
        +#95;#95;init#95;#95;(requested, available)
    }

    Exception <|-- LedgerError
    LedgerError <|-- InvalidAmountError
    LedgerError <|-- InvalidCurrencyError
    LedgerError <|-- CurrencyMismatchError
    LedgerError <|-- InvalidAccountSettingError
    LedgerError <|-- InsufficientFundsError

    Money ..> InvalidAmountError : raises
    Money ..> InvalidCurrencyError : raises
    Money ..> CurrencyMismatchError : raises
    Account ..> InvalidAmountError : raises
    Account ..> CurrencyMismatchError : raises
    Account ..> InvalidAccountSettingError : raises
    Account ..> InsufficientFundsError : raises
```

## Design notes

- **Money is exact.** Amounts are `Decimal` values rounded to cents, built from text, whole numbers or `Decimal`, never from `float`, because a float cannot store most cent values exactly. Adding or comparing two different currencies raises `CurrencyMismatchError` instead of giving a wrong answer.
- **One sign convention for every account.** A positive balance is money you have; a negative balance is money you owe. A credit card starts at $0.00, spending makes its balance negative, and a payment brings it back towards zero. The same rule lets one `withdraw()` method serve every account: it allows any amount up to `available_funds()`, which each account type defines (the balance for savings, the balance plus the overdraft limit for checking, the credit limit plus the balance for a credit card).
- **Optional features are mixins.** Interest and overdraft protection are features an account can have, not kinds of account, so they are mixin classes that any account type can reuse.

_Planned: all-or-nothing transfers, atomic saves and where data is stored._

## Known limitations

_Planned: what Ledger does not do._

## License

MIT. See [LICENSE](LICENSE).
