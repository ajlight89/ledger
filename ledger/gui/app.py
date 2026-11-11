"""The main window: the list of accounts and a button for each action."""

import tkinter as tk
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from tkinter import messagebox, ttk
from uuid import UUID

from ledger.cli import setup_logging
from ledger.core import storage
from ledger.core.accounts import CheckingAccount, CreditCardAccount, SavingsAccount
from ledger.core.book import Book
from ledger.core.categories import Category
from ledger.core.exceptions import LedgerError, ValidationError
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
        ttk.Button(buttons, text="Open account", command=self.show_open_account).pack(
            side="left"
        )

        ttk.Button(buttons, text="Deposit", command=self.show_deposit).pack(
            side="left", padx=(5, 0)
        )
        ttk.Button(buttons, text="Withdraw", command=self.show_withdraw).pack(
            side="left", padx=(5, 0)
        )

        ttk.Button(buttons, text="Exit", command=root.destroy).pack(side="right")

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

        self.refresh()

    def refresh(self) -> None:
        """Clear the list and fill it again, keeping the selected row selected."""
        selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        for row, account in enumerate(self.book.accounts):
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

    def selected_account(self):
        """Return the account selected in the list; ValidationError if none."""
        selection = self.tree.selection()
        if not selection:
            raise ValidationError("Select an account in the list first.")
        return self.book.get_account(UUID(selection[0]))

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

        self.center_over(app.root)
        self.deiconify()

        self.wait_visibility()  # a window must be showing before it can grab
        self.grab_set()  # the main window ignores clicks until this closes

    def center_over(self, parent: tk.Misc) -> None:
        """Move the dialog to the middle of the parent window."""
        self.update_idletasks()  # let Tk work out the dialog's size first
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 2
        self.geometry(f"+{x}+{y}")

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
