# Library Management System (CS 4347, Milestone 2)

Python + MySQL backend. See the team work plan for member assignments.

## Setup
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in your local MySQL credentials.

4. Make sure MySQL is running, then from the repo root: `python -m database.import_data`
   (creates the `library` database, applies `database/schema.sql`, loads the CSVs; loans and fines stay empty).
5. Run tests: `python -m unittest discover tests` (uses a throwaway `library_test` database).

Connection: `from database.database import get_connection`. Search: `from services.search import search_books`.
Service functions return `{success, message, data}`. Active loan = `Date_in IS NULL`.

## Workflow
One branch per member (`member1-search`, `member2-loans`, ...). Open a PR into `main`.
