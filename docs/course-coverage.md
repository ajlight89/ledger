# Course coverage

This table maps every topic in the CPTR212 Object Oriented Programming outline to the place in Ledger where it appears. The **Where in the code** column is filled in as each part is built, so a reader can jump straight to the example.

**Depth:** **Core** means the topic is built into the product. **Light** means a small, deliberate example. **Report** means it is covered mainly in the written report.

| Wk | Course topic | How Ledger uses it | Depth | Where in the code |
|---|---|---|---|---|
| 1 | Python refresher | Lists and dicts throughout: category rules, import reports, JSON loading | Light | |
| 2 | Intro to OOP, real-world modelling | Accounts, transactions and money modelled as objects. The report compares a procedural `transfer(dict, dict, amount)` with `Ledger.transfer()` | Report | |
| 3 | Classes and objects | Every class in `core`: `__init__`, `self`, instance attributes and methods | Core | |
| 4 | Encapsulation and access control | Protected `_transactions` (by convention) and name-mangled `__account_id` (private). A test shows `acct._Account__account_id` is the only way in | Core | |
| 5 | Getters, setters, `@property` | Validated `interest_rate`, `overdraft_limit`, `credit_limit` and `name`; read-only `balance`. The report shows the `get_rate()`/`set_rate()` version that was replaced | Core | |
| 6 | Inheritance basics | Shared `deposit()` and `withdraw()` in `Account`; subclasses extend them with `super()` | Core | |
| 7 | Advanced inheritance and MRO | Hierarchical (several accounts from `Account`), multilevel (`Account` → `DepositAccount` → `SavingsAccount`) and multiple (mixins). The report prints each `__mro__` | Core | |
| 8 | Overriding, polymorphism, duck typing | Each account type overrides `_check_withdrawal()`; `net_worth()` loops over mixed account types; the importer accepts anything iterable that yields row dicts | Core | |
| 9 | Special methods, operator overloading | `Money`: `+`, `-`, `*`, negation, `==`, `<`, `str`, `repr`, `hash`; `Account.__len__`, `__iter__`, `__repr__` | Core | |
| 10 | Abstraction; composition vs inheritance | `Account(ABC)`. A `Ledger` has accounts, and an importer has a column profile and a rule set (composition, not subclassing) | Core | |
| 11 | Exception handling | `LedgerError` hierarchy; `raise CSVFormatError(...) from err`; `try`/`except`/`else`/`finally` in import and save; the GUI shows `LedgerError` messages | Core | |
| 12 | File handling in an OOP context | `JsonStorage` class with atomic writes; CSV import; `with` blocks; a `ledger.batch()` context manager if time allows | Core | |
| 13 | Iterators, generators, decorators | `MonthRange` class with `__iter__`/`__next__`; `monthly_statement()` generator; `@logged`, and `@validate_amount` if time allows | Core | |
| 14 | OOP design principles | `core` and `gui` packages; one job per module (cohesion); the GUI calls only the `Ledger` service (low coupling). Design section in the report | Core | [`src/ledger/core/`](../src/ledger/core/) and [`src/ledger/gui/`](../src/ledger/gui/) are separate packages, and each module's docstring states its single job. `SmokeTest.test_core_has_no_tkinter_imports` in [`tests/test_smoke.py`](../tests/test_smoke.py) fails if `core` ever imports tkinter |
| 15 | Testing and debugging | `unittest` suite from the start; the report's debugging log covers two or three real bugs, how they were found and the regression test added for each | Core | [`tests/`](../tests/) holds the `unittest` suite, run with `python -m unittest discover -s tests`. First tests: `SmokeTest` in [`tests/test_smoke.py`](../tests/test_smoke.py) |
