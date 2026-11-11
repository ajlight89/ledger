"""The main window: the list of accounts and a button for each action."""

import tkinter as tk
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from uuid import UUID

from ledger.cli import setup_logging
from ledger.core import importer, reports, storage
from ledger.core.accounts import CheckingAccount, CreditCardAccount, SavingsAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import DuplicateAccountError, LedgerError, ValidationError
from ledger.core.money import Money

# Account.TYPE (the name saved in the data file) -> the label shown in the list.
TYPE_LABELS = {
    "checking": "Checking",
    "savings": "Savings",
    "credit_card": "Credit Card",
}

# Labels a user may pick; Transfer and Interest are recorded by Ledger itself.
CATEGORY_CHOICES = [
    str(c) for c in Category if c not in (Category.TRANSFER, Category.INTEREST)
]

# ----- Helper functions -----


def parse_money(text: str) -> Money:
    """Turn text such as '$1,200.50' into Money; bad text raises InvalidAmountError."""
    return Money.from_str(text.strip().replace("$", "").replace(",", ""))


def parse_rate(text: str) -> Decimal:
    """Turn text such as '4.5' or '4.5%' into a Decimal; bad text raises ValidationError."""
    cleaned = text.strip().replace("%", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation as err:
        raise ValidationError(f"'{cleaned}' is not a number.") from err


def set_enabled(widget: ttk.Widget, enabled: bool) -> None:
    """Turn a ttk widget on or off; "!disabled" means "not disabled"."""
    widget.state(["!disabled"] if enabled else ["disabled"])


def parse_date(text: str) -> date:
    """Turn MM/DD/YYYY text into a date; blank means today; bad text raises ValidationError."""
    cleaned = text.strip()
    if not cleaned:
        return date.today()
    try:
        return datetime.strptime(cleaned, "%m/%d/%Y").date()
    except ValueError as err:
        raise ValidationError(f"'{cleaned}' is not a date like 11/10/2026.") from err


def parse_month(text: str) -> tuple[int, int]:
    """Turn MM/YYYY text into (year, month); blank means this month."""
    cleaned = text.strip()
    if not cleaned:
        today = date.today()
        return today.year, today.month
    try:
        day = datetime.strptime(cleaned, "%m/%Y")
    except ValueError as err:
        raise ValidationError(f"'{cleaned}' is not a month like 10/2026.") from err
    return day.year, day.month


def center_over(window: tk.Toplevel, parent: tk.Misc) -> None:
    """Move window to the middle of the parent window."""
    window.update_idletasks()  # let Tk work out the window's size first
    x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_reqwidth()) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_reqheight()) // 2
    window.geometry(f"+{x}+{y}")


def shows_errors(method):
    """Decorator for LedgerApp button handlers: show a LedgerError in a message box.

    Without it, an error in a button handler would only print a traceback
    in the terminal, and the user would see nothing happen.
    """

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except LedgerError as err:
            messagebox.showerror("Ledger", str(err), parent=self.root)

    return wrapper


# ----- Core application interface -----


class LedgerApp:
    """The main window. It shows the active accounts and asks the core to act."""

    def __init__(self, root: tk.Tk, book: Book) -> None:
        """Build the widgets inside root and fill the list from book."""
        self.root = root
        self.book = book
        root.title("Ledger")
        root.geometry("1280x720")
        root.minsize(640, 360)
        # A Style changes how every widget of a kind looks; "Treeview.Heading"
        # is the heading row of every Treeview. Segoe UI 9 is the Windows default.
        style = ttk.Style(root)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        # Packed before the list so the buttons keep their place when the
        # window gets smaller; the list then takes whatever space is left.
        buttons = ttk.Frame(root, padding=(10, 0, 10, 10))
        buttons.pack(side="bottom", fill="x")
        # Buttons for active accounts, in the same order as the text menu.
        self.active_buttons = []
        for text, command in (
            ("Open account", self.show_open_account),
            ("Deposit", self.show_deposit),
            ("Withdraw", self.show_withdraw),
            ("Transfer", self.show_transfer),
            ("Rename", self.show_rename),
            ("Archive", self.show_archive),
            ("Import CSV", self.show_import),
        ):
            button = ttk.Button(buttons, text=text, command=command)
            button.pack(side="left", padx=(0, 5))
            self.active_buttons.append(button)
        self.restore_button = ttk.Button(
            buttons, text="Restore", command=self.show_restore
        )

        # Reports work in both views (statements for archived accounts too).
        ttk.Button(buttons, text="Statement", command=self.show_statement).pack(
            side="left", padx=(0, 5)
        )
        ttk.Button(buttons, text="Spending", command=self.show_spending).pack(
            side="left", padx=(0, 5)
        )

        self.restore_button.pack(side="left", padx=(0, 5))
        ttk.Button(buttons, text="Exit", command=root.destroy).pack(side="right")

        # Ticking the box switches the list to archived accounts.
        self.show_archived = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            root,
            text="Show archived accounts",
            variable=self.show_archived,
            command=self.change_view,
        ).pack(side="top", anchor="w", padx=10, pady=(10, 0))

        # show="headings" hides the tree's own "#0" column, which keeps a
        # left indent for expand arrows that a flat list doesn't need.
        columns = ("name", "type", "balance")
        self.tree = ttk.Treeview(
            root, columns=columns, show="headings", selectmode="browse"
        )
        self.tree.heading("name", text="Account")
        self.tree.heading("type", text="Type")
        self.tree.heading("balance", text="Balance")
        # Text reads best from the left; money lines up on the right.
        for column, side in (("name", "w"), ("type", "w"), ("balance", "e")):
            self.tree.column(column, anchor=side)
            self.tree.heading(column, anchor=side)
        # Rows tagged "odd" get a light gray background (striped rows).
        self.tree.tag_configure("odd", background="#f0f0f0")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.change_view()

    def refresh(self) -> None:
        """Clear the list and fill it again, keeping the selected row selected."""
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for row, account in enumerate(self.shown_accounts()):
            stripe = ("odd",) if row % 2 == 1 else ()
            self.tree.insert(
                "",
                "end",
                iid=str(account.id),
                values=(
                    account.name,
                    TYPE_LABELS[account.TYPE],
                    str(account.balance),
                ),
                tags=stripe,
            )
        for iid in selected:
            if self.tree.exists(iid):  # gone if the account was archived
                self.tree.selection_set(iid)

    def shown_accounts(self) -> tuple:
        """The accounts the list shows: archived ones if the box is ticked."""
        if self.show_archived.get():
            return self.book.archived_accounts
        return self.book.accounts

    def change_view(self) -> None:
        """Switch the list, and turn on only the buttons that fit the view."""
        archived = self.show_archived.get()
        for button in self.active_buttons:
            set_enabled(button, not archived)
        set_enabled(self.restore_button, archived)
        self.refresh()

    def selected_account(self):
        """Return the account selected in the list; ValidationError if none."""
        selection = self.tree.selection()
        if not selection:
            raise ValidationError("Select an account in the list first.")
        selected_id = UUID(selection[0])
        for account in self.shown_accounts():
            if account.id == selected_id:
                return account
        # Every row comes from shown_accounts(), so this is never reached;
        # it keeps the promise that the method returns an account or raises.
        raise ValidationError("Select an account in the list first.")

    def show_open_account(self) -> None:
        """Show the Open account dialog."""
        OpenAccountDialog(self)

    @shows_errors
    def show_deposit(self) -> None:
        """Show the Deposit dialog for the selected account."""
        TransactionDialog(self, self.selected_account(), "Deposit")

    @shows_errors
    def show_withdraw(self) -> None:
        """Show the Withdraw dialog for the selected account."""
        TransactionDialog(self, self.selected_account(), "Withdraw")

    @shows_errors
    def show_transfer(self) -> None:
        """Show the Transfer dialog; From starts as the selected account, if any."""
        if len(self.book.accounts) < 2:
            raise ValidationError("A transfer needs at least two accounts.")
        source = self.selected_account() if self.tree.selection() else None
        TransferDialog(self, source)

    @shows_errors
    def show_rename(self) -> None:
        """Show the Rename dialog for the selected account."""
        RenameDialog(self, self.selected_account())

    @shows_errors
    def show_archive(self) -> None:
        """Ask first, then archive the selected account."""
        account = self.selected_account()
        question = f"Archive {account.name}? It can be restored later."
        if messagebox.askyesno("Ledger", question, parent=self.root):
            self.archive_account(account)

    @shows_errors
    def show_restore(self) -> None:
        """Restore the selected archived account, offering a new name if needed."""
        account = self.selected_account()
        try:
            self.restore_account(account)
        except DuplicateAccountError as err:
            question = f"{err}\n\nRestore it under a different name?"
            if messagebox.askyesno("Ledger", question, parent=self.root):
                RestoreDialog(self, account)

    @shows_errors
    def show_import(self) -> None:
        """Pick a CSV file and import its rows into the selected account."""
        account = self.selected_account()
        path = filedialog.askopenfilename(
            parent=self.root,
            title=f"Import into {account.name}",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:  # Cancel returns an empty string
            return
        count = self.import_csv(account, Path(path))
        if count:
            message = f"Imported {count} transactions into {account.name}."
        else:
            message = "No new transactions; every row was already in the account."
        messagebox.showinfo("Ledger", message, parent=self.root)

    @shows_errors
    def show_statement(self) -> None:
        """Ask for a month, then show the selected account's statement."""
        account = self.selected_account()
        title = f"Statement: {account.name}"

        def show(year: int, month: int) -> None:
            ReportWindow(self.root, title, self.statement_text(account, year, month))

        MonthDialog(self, title, show)

    def show_spending(self) -> None:
        """Ask for a month, then show spending by category."""

        def show(year: int, month: int) -> None:
            text = self.spending_text(year, month)
            ReportWindow(self.root, "Spending by category", text)

        MonthDialog(self, "Spending by category", show)

    def open_account(
        self, kind: str, name: str, overdraft: bool, rate_text: str, limit_text: str
    ) -> None:
        """Create the account, add it, save, and select its row.

        Every value is checked before add_account, so a refusal leaves the
        book unchanged and nothing is saved.
        """
        today = date.today()
        if kind == "Checking":
            account = CheckingAccount(name, today, overdraft_enabled=overdraft)
        elif kind == "Savings":
            account = SavingsAccount(name, today)
            account.interest_rate = parse_rate(rate_text)
        else:
            limit = parse_money(limit_text)
            account = CreditCardAccount(name, today, credit_limit=limit)
            account.interest_rate = parse_rate(rate_text)
        self.book.add_account(account)
        storage.save_book(self.book)
        self.refresh()
        self.tree.selection_set(str(account.id))

    def record_transaction(
        self, method, amount_text: str, date_text: str, label: str, description: str
    ) -> None:
        """Call method (account.deposit or account.withdraw), then save.

        The account checks the amount and description; if it refuses,
        nothing is recorded and nothing is saved.
        """
        amount = parse_money(amount_text)
        on = parse_date(date_text)
        method(amount, on, Category(label), description)
        storage.save_book(self.book)
        self.refresh()

    def transfer(
        self, source, destination, amount_text: str, date_text: str, description: str
    ) -> None:
        """Move money between two active accounts, then save."""
        amount = parse_money(amount_text)
        on = parse_date(date_text)
        self.book.transfer(amount, source.id, destination.id, on, description)
        storage.save_book(self.book)
        self.refresh()

    def rename_account(self, account, new_name: str) -> None:
        """Rename the account, then save; the core refuses a taken or blank name."""
        self.book.rename_account(account.id, new_name)
        storage.save_book(self.book)
        self.refresh()

    def archive_account(self, account) -> None:
        """Archive the account, then save; the core refuses unless it is $0.00."""
        self.book.archive_account(account.id)
        storage.save_book(self.book)
        self.refresh()

    def restore_account(self, account, new_name: str | None = None) -> None:
        """Restore an archived account, under new_name if one is given.

        If anything is refused, the account keeps its old name, so no
        half-made change is left in memory (the same rule as the menu).
        """
        original_name = account.name
        try:
            if new_name is not None:
                account.name = new_name
            self.book.restore_account(account.id)
        except LedgerError:
            account.name = original_name
            raise
        storage.save_book(self.book)
        self.refresh()

    def import_csv(self, account, path: Path) -> int:
        """Import the file into the account, save if anything was added,
        and return how many transactions were added."""
        added = importer.import_csv(account, path)
        if added:
            storage.save_book(self.book)
            self.refresh()
        return len(added)

    def statement_text(self, account, year: int, month: int) -> str:
        """The account's statement for one month, as lines of text."""
        opening = reports.opening_balance(account, year, month)
        lines = [
            f"{account.name}: {date(year, month, 1):%B %Y}",
            f"Opening balance: {opening}",
            "",
            f"{'Date':<10}  {'Description':<30}  {'Amount':>12}  {'Balance':>12}",
        ]
        closing = opening
        count = 0
        for line in reports.statement_lines(account, year, month):
            lines.append(
                f"{line.date:%m/%d/%Y}  {line.description:<30.30}  "
                f"{line.amount!s:>12}  {line.balance!s:>12}"
            )
            closing = line.balance
            count += 1
        if count == 0:
            lines.append("No transactions this month.")
        lines.append("")
        lines.append(f"Closing balance: {closing}")
        return "\n".join(lines)

    def spending_text(self, year: int, month: int) -> str:
        """Spending in each category for one month, largest first, as text."""
        totals = reports.spending_by_category(self.book, year, month)
        lines = [f"Spending for {date(year, month, 1):%B %Y}", ""]
        if not totals:
            lines.append("No spending this month.")
            return "\n".join(lines)
        for category, amount in totals.items():
            lines.append(f"{category!s:<20}  {amount!s:>12}")
        total = sum(totals.values(), Money.zero())
        lines.append(f"{'Total':<20}  {total!s:>12}")
        return "\n".join(lines)


class Dialog(tk.Toplevel, ABC):
    """A small window with OK and Cancel. Subclasses add fields and the action.

    ok() is a template method: it calls submit(), which each subclass
    writes, and handles a LedgerError the same way for every dialog.
    """

    def __init__(self, app: LedgerApp, title: str) -> None:
        """Build the dialog over the main window and send all clicks to it."""
        super().__init__(app.root)
        self.withdraw()
        self.app = app
        self.title(title)
        self.resizable(False, False)
        self.transient(app.root)  # stays on top of the main window

        self.body = ttk.Frame(self, padding=10)
        self.body.pack(fill="both", expand=True)
        self.build()

        buttons = ttk.Frame(self, padding=(10, 0, 10, 10))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="OK", command=self.ok).pack(side="right", padx=(0, 5))
        self.bind("<Return>", lambda event: self.ok())
        self.bind("<Escape>", lambda event: self.destroy())

        center_over(self, app.root)
        self.deiconify()

        self.wait_visibility()  # a window must be showing before it can grab
        self.grab_set()  # the main window ignores clicks until this closes

    def add_row(self, row: int, label: str, widget: ttk.Widget) -> None:
        """Put a label in column 0 and the widget in column 1 of the row."""
        ttk.Label(self.body, text=label).grid(
            row=row, column=0, sticky="w", padx=(0, 8), pady=3
        )
        widget.grid(row=row, column=1, sticky="ew", pady=3)

    @abstractmethod
    def build(self) -> None:
        """Add this dialog's fields to self.body."""

    @abstractmethod
    def submit(self) -> None:
        """Read the fields and ask the app to act; may raise LedgerError."""

    def ok(self) -> None:
        """Try the action; on a LedgerError show it and keep the dialog open."""
        try:
            self.submit()
        except LedgerError as err:
            messagebox.showerror("Ledger", str(err), parent=self)
            return
        self.destroy()


class OpenAccountDialog(Dialog):
    """Ask for the new account's type, name and the details that type needs."""

    def __init__(self, app: LedgerApp) -> None:
        super().__init__(app, "Open account")

    def build(self) -> None:
        self.kind_var = tk.StringVar(value="Checking")
        self.name_var = tk.StringVar()
        self.overdraft_var = tk.BooleanVar(value=False)
        self.rate_var = tk.StringVar(value="0")
        self.limit_var = tk.StringVar()

        kind_box = ttk.Combobox(
            self.body,
            textvariable=self.kind_var,
            values=list(TYPE_LABELS.values()),
            state="readonly",
        )
        kind_box.bind("<<ComboboxSelected>>", self.update_fields)
        self.add_row(0, "Type:", kind_box)

        name_entry = ttk.Entry(self.body, textvariable=self.name_var, width=30)
        self.add_row(1, "Name:", name_entry)
        name_entry.focus_set()

        self.overdraft_box = ttk.Checkbutton(
            self.body, text="Allow overdraft down to -$500", variable=self.overdraft_var
        )
        self.add_row(2, "Overdraft:", self.overdraft_box)

        self.rate_entry = ttk.Entry(self.body, textvariable=self.rate_var)
        self.add_row(3, "Interest rate (%):", self.rate_entry)

        self.limit_entry = ttk.Entry(self.body, textvariable=self.limit_var)
        self.add_row(4, "Credit limit:", self.limit_entry)

        self.update_fields()

    def update_fields(self, event: tk.Event | None = None) -> None:
        """Turn on only the fields the chosen account type uses."""
        kind = self.kind_var.get()
        set_enabled(self.overdraft_box, kind == "Checking")
        set_enabled(self.rate_entry, kind != "Checking")
        set_enabled(self.limit_entry, kind == "Credit Card")

    def submit(self) -> None:
        self.app.open_account(
            self.kind_var.get(),
            self.name_var.get(),
            self.overdraft_var.get(),
            self.rate_var.get(),
            self.limit_var.get(),
        )


class TransactionDialog(Dialog):
    """Ask for a deposit's or withdrawal's amount, date, category and description."""

    def __init__(self, app: LedgerApp, account, action: str) -> None:
        self.account = account
        self.action = action  # "Deposit" or "Withdraw"
        super().__init__(app, f"{action}: {account.name}")

    def build(self) -> None:
        default = "Income" if self.action == "Deposit" else "Other"
        self.amount_var = tk.StringVar()
        self.date_var = tk.StringVar(value=f"{date.today():%m/%d/%Y}")
        self.category_var = tk.StringVar(value=default)
        self.description_var = tk.StringVar()

        amount_entry = ttk.Entry(self.body, textvariable=self.amount_var, width=30)
        self.add_row(0, "Amount:", amount_entry)
        amount_entry.focus_set()
        self.add_row(
            1, "Date (MM/DD/YYYY):", ttk.Entry(self.body, textvariable=self.date_var)
        )
        self.add_row(
            2,
            "Category:",
            ttk.Combobox(
                self.body,
                textvariable=self.category_var,
                values=CATEGORY_CHOICES,
                state="readonly",
            ),
        )
        self.add_row(
            3,
            "Description:",
            ttk.Entry(self.body, textvariable=self.description_var),
        )
        if self.account.TYPE == "credit_card":
            if self.action == "Deposit":
                note = "On a credit card, a deposit is a payment."
            else:
                note = "On a credit card, a withdrawal is a charge."
            ttk.Label(self.body, text=note).grid(row=4, column=1, sticky="w")

    def submit(self) -> None:
        if self.action == "Deposit":
            method = self.account.deposit
        else:
            method = self.account.withdraw
        self.app.record_transaction(
            method,
            self.amount_var.get(),
            self.date_var.get(),
            self.category_var.get(),
            self.description_var.get(),
        )


class TransferDialog(Dialog):
    """Ask which accounts the money moves between, how much, when, and why."""

    def __init__(self, app: LedgerApp, source=None) -> None:
        self.source = source
        # Active names are unique, so each name leads to exactly one account.
        self.accounts = {a.name: a for a in app.book.accounts}
        super().__init__(app, "Transfer")

    def build(self) -> None:
        self.from_var = tk.StringVar(value=self.source.name if self.source else "")
        self.to_var = tk.StringVar()
        self.amount_var = tk.StringVar()
        self.date_var = tk.StringVar(value=f"{date.today():%m/%d/%Y}")
        self.description_var = tk.StringVar()

        names = list(self.accounts)
        from_box = ttk.Combobox(
            self.body,
            textvariable=self.from_var,
            values=names,
            state="readonly",
            width=28,
        )
        self.add_row(0, "From account:", from_box)
        to_box = ttk.Combobox(
            self.body,
            textvariable=self.to_var,
            values=names,
            state="readonly",
            width=28,
        )
        self.add_row(1, "To account:", to_box)
        # Start where the next choice is needed.
        if self.source:
            to_box.focus_set()
        else:
            from_box.focus_set()
        self.add_row(2, "Amount:", ttk.Entry(self.body, textvariable=self.amount_var))
        self.add_row(
            3, "Date (MM/DD/YYYY):", ttk.Entry(self.body, textvariable=self.date_var)
        )
        self.add_row(
            4,
            "Description:",
            ttk.Entry(self.body, textvariable=self.description_var),
        )

    def submit(self) -> None:
        # dict.get returns None for a name that isn't there (nothing chosen yet).
        source = self.accounts.get(self.from_var.get())
        destination = self.accounts.get(self.to_var.get())
        if source is None or destination is None:
            raise ValidationError("Choose both accounts.")
        self.app.transfer(
            source,
            destination,
            self.amount_var.get(),
            self.date_var.get(),
            self.description_var.get(),
        )


class RenameDialog(Dialog):
    """Ask for an account's new name, starting from its current one."""

    TITLE = "Rename"

    def __init__(self, app: LedgerApp, account) -> None:
        self.account = account
        super().__init__(app, f"{self.TITLE}: {account.name}")

    def build(self) -> None:
        self.name_var = tk.StringVar(value=self.account.name)
        name_entry = ttk.Entry(self.body, textvariable=self.name_var, width=30)
        self.add_row(0, "New name:", name_entry)
        name_entry.focus_set()
        name_entry.select_range(0, "end")  # typing replaces the old name

    def submit(self) -> None:
        self.app.rename_account(self.account, self.name_var.get())


class RestoreDialog(RenameDialog):
    """The same window as RenameDialog, but OK restores under the new name."""

    TITLE = "Restore under a new name"

    def submit(self) -> None:
        self.app.restore_account(self.account, self.name_var.get())


class MonthDialog(Dialog):
    """Ask for a month, then call on_month(year, month) with it."""

    def __init__(self, app: LedgerApp, title: str, on_month) -> None:
        self.on_month = on_month
        super().__init__(app, title)

    def build(self) -> None:
        self.month_var = tk.StringVar(value=f"{date.today():%m/%Y}")
        month_entry = ttk.Entry(self.body, textvariable=self.month_var, width=12)
        self.add_row(0, "Month (MM/YYYY):", month_entry)
        month_entry.focus_set()
        month_entry.select_range(0, "end")

    def submit(self) -> None:
        year, month = parse_month(self.month_var.get())
        self.on_month(year, month)


class ReportWindow(tk.Toplevel):
    """A read-only window that shows a report in a fixed-width font."""

    def __init__(self, parent: tk.Misc, title: str, text: str) -> None:
        super().__init__(parent)
        self.withdraw()  # stay hidden until it has been placed
        self.title(title)
        self.transient(parent)

        ttk.Button(self, text="Close", command=self.destroy).pack(
            side="bottom", anchor="e", padx=10, pady=10
        )
        # Consolas gives every character the same width, so f-string
        # column widths line up as they do in the terminal.
        box = tk.Text(
            self,
            font=("Consolas", 10),
            wrap="none",
            width=80,
            height=24,
            padx=10,
            pady=10,
        )
        scrollbar = ttk.Scrollbar(self, command=box.yview)
        box.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        box.pack(fill="both", expand=True)
        box.insert("1.0", text)
        box.configure(state="disabled")  # read-only
        self.bind("<Escape>", lambda event: self.destroy())

        center_over(self, parent)
        self.deiconify()
        self.focus_set()


def main() -> None:
    """Load the book, post any interest due, then show the window."""
    setup_logging()
    root = tk.Tk()
    try:
        book = storage.load_book()
        if book.accrue_all_interest(date.today()):
            storage.save_book(book)
    except LedgerError as err:
        root.withdraw()
        messagebox.showerror("Ledger", str(err))
        root.destroy()
        return
    LedgerApp(root, book)
    root.mainloop()
