# AI usage notes

Ledger is being built with AI assistance via Claude by Anthropic. These notes record what the AI provided, what I decided or changed myself, and how each piece was checked, so a reader can see which work is mine.

## How AI was used

- **Tool:** Claude (Anthropic), used as an assistant in a claude.ai Project that holds the abstract, the project plan, my environment notes and a progress file. One chat per phase.
- **Way of working:** each part is built in small steps. For each step, Claude provides complete code, an explanation of the object-oriented concept behind it, and a command to verify it. I enter the code into VS Code myself, run it, review and edit it, and write the commits.
- **Editor:** GitHub Copilot's inline suggestions are turned off in this repository's VS Code settings.
- **Decisions:** where Claude recommended a design choice, these notes say so, along with the decision I made.

## Log

One row per phase.

| Date | Work | Claude provided | What I decided or changed | Verified by |
| --- | --- | --- | --- | --- |
| 2026-10-10 to 2026-10-13 | Starting files | Project configuration (`pyproject.toml`, VS Code settings, package layout); the `Money` value class and the exception hierarchy, with 61 unittest tests; smoke tests, including a check that `core` never imports tkinter; the README class diagram | Decided that `Money` rejects floats instead of converting them, and that it is a hand-written class instead of a `@dataclass`. Reworded docstrings and comments, renamed tests, and fixed problems found in review (a lost word in a docstring, nested `with` blocks that disabled `subTest`, a Mermaid diagram that dropped double underscores) | `python -W error -m unittest`: all tests passing with no warnings; class diagram checked on GitHub |
| 2026-10-17 | Phase 1: repository setup and accounts | Setup commands for the virtual environment, Git and GitHub; two new exceptions (`InvalidAccountSettingError`, `InsufficientFundsError`); `Account(ABC)`, `CheckingAccount`, `SavingsAccount`, `CreditCardAccount`; `InterestMixin` and `OverdraftProtectionMixin`; 55 new tests; two README class diagrams and design notes; a review of my typed files against its own copies; first versions of the report and slides | Typed all the code myself instead of downloading it. Accepted Claude's proposals for one sign convention for every account, mixins without `__init__`, a `Decimal` interest rate, and the error types. Used `+=` and `-=` for balance updates. Chose my own commit messages and repository description, and edited the README wording. Fixed my typing errors: three in the tests, caught by the test runs, and typos in an error message and docstrings, found by Claude's review | `python -m unittest`: 116 tests passing; checks with `python -c`; class diagrams checked on GitHub |
| 2026-10-17 | Claude's mistakes, Phase 1 | In step 2, Claude put unnecessary quotes on two attribute annotations (`self.requested: "Money"`) | Removed the quotes; the quotes in the `__init__` signature stay because they are needed | Ruff flagged the quotes; Claude confirmed the fix by testing both versions |
