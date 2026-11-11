# GUI Checklist

The automated tests in `test_gui.py` call the window's methods directly. This
checklist covers what they cannot: layout, dialogs on screen, focus and keys.
Run it with `python -m ledger` before each GUI commit and before a release.
Use throwaway account names such as "GUI Test".

## Start and exit

- [ ] The window opens at 1280×720 with bold headings: Account, Type, Balance.
- [ ] Names and types are left-aligned; balances are right-aligned.
- [ ] Every second row has a light gray background.
- [ ] Shrinking the window keeps the button row visible.
- [ ] Exit closes the window. After reopening, every change is still there.
- [ ] A damaged data file shows an error box and Ledger does not start.
      (Copy `ledger.json` aside, put `{` in it, launch, then copy the original back.)

## Dialogs (every dialog)

- [ ] The dialog opens centered over the main window, with no flash elsewhere.
- [ ] After moving the main window, the next dialog follows it.
- [ ] The main window ignores clicks while a dialog is open.
- [ ] Enter presses OK; Esc and Cancel close without changing anything.
- [ ] A refused value shows an error box, and the dialog stays open with the typing intact.

## Open account

- [ ] Type starts on Checking; the rate and limit fields are grayed out.
- [ ] Savings turns on the rate field; Credit Card turns on rate and limit;
      overdraft is grayed out for both.
- [ ] A rate such as `abc` is refused.
- [ ] A name already in use (in any capitals) is refused.
- [ ] A valid account appears in the list, selected.

## Deposit and withdraw

- [ ] With no row selected, Deposit and Withdraw show
      "Select an account in the list first."
- [ ] The dialog title names the account; the date starts as today.
- [ ] A deposit updates the balance and the row stays selected.
- [ ] Withdrawing more than the balance (overdraft off) is refused.
- [ ] A blank description is refused; a date such as `2026-11-05` is refused.
- [ ] For a credit card, the dialog explains that a deposit is a payment
      and a withdrawal is a charge; a charge makes the balance more negative.

## Transfer

- [ ] With no row selected, From starts empty; OK with an empty account shows
      "Choose both accounts."
- [ ] With a row selected, From starts as that account and the cursor is on To.
- [ ] The same account in From and To is refused.
- [ ] An amount over the balance is refused; the dialog stays open.
- [ ] A valid transfer updates both rows.

## Rename

- [ ] The current name starts highlighted, so typing replaces it.
- [ ] A name already in use (in any capitals) or a blank name is refused.

## Archive and restore

- [ ] "Show archived accounts" switches the list; every button except Restore
      and Exit is grayed out. Unticking reverses this.
- [ ] Restore is grayed out in the normal view.
- [ ] Archive asks yes/no first; No changes nothing.
- [ ] Archiving an account that is not $0.00 (including a card that owes) is refused.
- [ ] A $0.00 account moves to the archived view.
- [ ] Restore brings it back to the normal view.
- [ ] Name clash: after archiving a $0.00 account and opening a new one with the
      same name, restoring the old one offers a new name. No leaves it archived;
      a name in use is refused with the dialog left open; a free name restores it.
