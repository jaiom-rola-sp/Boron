# Library Management System (CS 4347, Milestone 2)

Backend logic for a library system used by librarians: book search, checkout/check-in,
borrower registration, and fines. Python + MySQL. The GUI is Milestone 3.

## Requirements
- Python 3.13 (tested on 3.13.12; 3.10+ should work)
- MySQL 8+ (tested on the Homebrew build, `mysql Ver 26.10.0`)
- Python packages (see `requirements.txt`): `mysql-connector-python`, `python-dotenv`

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
```
Make sure MySQL is running (macOS Homebrew: `brew services start mysql`), then load the data:
```bash
python -m database.import_data
```
This creates the `library` database, applies `database/schema.sql` and loads the four CSVs in `data/`
(25,001 books, 15,548 authors, 30,232 book-author links, 1,000 borrowers).
`BOOK_LOANS` and `FINES` start empty. **Re-running it wipes and reloads all tables.**
All data is fake. Never commit `.env`.

## Run the command-line menu
```bash
python main.py
```
A simple text menu to try every feature: search books, check out/in, find loans, create a borrower,
refresh fines, view fines and pay fines. It only calls the service functions below.

## Run the tests
```bash
python -m unittest discover tests
```
Tests create and drop their own throwaway databases, so your `library` data is not touched.
The MySQL user in `.env` needs permission to create databases.

## Project layout
```
data/        books.csv, authors.csv, book_authors.csv, borrowers.csv (normalized in Milestone 1)
database/    schema.sql, database.py (get_connection, run_schema), import_data.py
services/    search.py, loans.py, borrowers.py, fine_calculator.py, fine_payment.py
main.py      command-line test menu
tests/       one test file per service, plus test_integration.py (end-to-end flow)
source_code/ Milestone 1 normalization scripts
```

## Service functions
Every function returns `{"success": bool, "message": str, "data": ...}` and never prints or prompts.
An active loan is a `BOOK_LOANS` row with `Date_in IS NULL`. Money is `DECIMAL(10,2)` / Python `Decimal`.

| Module | Functions | Notes |
|---|---|---|
| `services/search.py` | `search_books(query)` | Case-insensitive substring match on ISBN, title and author; every word must match something. Returns ISBN, title, comma-separated authors, availability. |
| `services/loans.py` | `checkout(isbn, card_id)`, `search_loans(query)`, `checkin(loan_ids)` | Max 3 active loans, no double checkout, no checkout with unpaid fines (fines are refreshed first), due date = today + 14 days. Check-in takes 1-3 loans at once. |
| `services/borrowers.py` | `create_borrower(name, ssn, address, phone)`, `generate_card_id()` | Name, SSN and address required; duplicate SSN rejected; IDs follow the `ID000001` format. |
| `services/fine_calculator.py` | `calculate_fine(due_date, date_in=None)`, `refresh_fines()`, `has_unpaid_fines(card_id)` | $0.25 per late day. Returned books use the return date, outstanding books use today. Paid fines are never changed. |
| `services/fine_payment.py` | `get_fines(include_paid=False)`, `get_borrower_fines(card_id)`, `pay_fines(card_id)` | Fines grouped per borrower with payable vs. unreturned-book totals. Full payment only, in one transaction; blocked while any fined book is still out. |

Quick try:
```bash
python -c "from services.search import search_books; print(search_books('william')['data'][:3])"
```

## Team workflow
One branch per member, open a PR into `main`, and merge `main` into your branch before opening the PR.
Do not edit another member's files without telling them.

## Known open question
Whether fines on unreturned books should block payment of fines on returned books is still to be
confirmed with the TA. Current behavior: payment is blocked until every fined book is returned.
