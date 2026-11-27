"""Command-line test menu for Milestone 2 (Member 3 -- integration).

Run from the repo root:  python main.py
"""
import importlib

from services.borrowers import create_borrower


def _fn(module, name):
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError):
        return None


def show(result):
    print(("\n[OK] " if result.get("success") else "\n[ERROR] ") + str(result.get("message", "")))
    data = result.get("data")
    if isinstance(data, list):
        for i, row in enumerate(data, 1):
            print(f"{i:>3}. " + (" | ".join(f"{k}: {v}" for k, v in row.items()) if isinstance(row, dict) else str(row)))
    elif data not in (None, {}):
        print(data)


def call(module, name, *args, **kw):
    fn = _fn(module, name)
    if fn is None:
        print(f"\n{module}.{name}() isn't available yet (not merged?).")
        return
    show(fn(*args, **kw))


def do_search():
    call("services.search", "search_books", input("Search (ISBN/title/author): "))


def do_checkout():
    call("services.loans", "checkout", input("ISBN: ").strip(), input("Card ID: ").strip())


def do_find_loans():
    call("services.loans", "search_loans", input("ISBN / card ID / borrower name: "))


def do_checkin():
    raw = [x.strip() for x in input("Loan ID(s), comma-separated (max 3): ").split(",") if x.strip()]
    try:
        ids = [int(x) for x in raw]
    except ValueError:
        print("\n[ERROR] Loan IDs must be whole numbers.")
        return
    call("services.loans", "checkin", ids)


def do_new_borrower():
    show(create_borrower(
        input("Name: "), input("SSN: "), input("Address: "), input("Phone (optional): ")))


def do_refresh():
    call("services.fine_calculator", "refresh_fines")


def do_fines():
    show_paid = input("Include paid fines? (y/N): ").strip().lower() == "y"
    call("services.fine_payment", "get_fines", include_paid=show_paid)


def do_borrower_fines():
    call("services.fine_payment", "get_borrower_fines", input("Card ID: ").strip())


def do_pay():
    call("services.fine_payment", "pay_fines", input("Card ID: ").strip())


MENU = [
    ("Search books", do_search),
    ("Check out a book", do_checkout),
    ("Find active loans", do_find_loans),
    ("Check in book(s)", do_checkin),
    ("Create borrower", do_new_borrower),
    ("Refresh fines", do_refresh),
    ("View all fines (grouped by borrower)", do_fines),
    ("View one borrower's fines", do_borrower_fines),
    ("Pay fines", do_pay),
]


def main():
    while True:
        print("\n=== Library Management ===")
        for i, (label, _) in enumerate(MENU, 1):
            print(f"{i}. {label}")
        print("0. Quit")
        choice = input("> ").strip()
        if choice == "0":
            break
        if choice.isdigit() and 1 <= int(choice) <= len(MENU):
            try:
                MENU[int(choice) - 1][1]()
            except Exception as e:
                print(f"\n[ERROR] {e}")
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()