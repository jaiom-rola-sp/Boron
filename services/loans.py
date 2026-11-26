from datetime import date, timedelta
from database.database import get_connection


def _result(success, message, data=None):
    return {"success": success, "message": message, "data": data if data is not None else []}


class LoanError(Exception):
    pass


def _write(operation, conn):
    own = conn is None
    cur = None
    started = False
    try:
        conn = conn or get_connection()
        if conn.in_transaction:
            return _result(False, "Use a connection without an active transaction.")
        conn.start_transaction(isolation_level="READ COMMITTED")
        started = True
        cur = conn.cursor(dictionary=True)
        data, message = operation(cur)
        conn.commit()
        return _result(True, message, data)
    except LoanError as exc:
        if started:
            conn.rollback()
        return _result(False, str(exc))
    except Exception as exc:
        if started:
            conn.rollback()
        return _result(False, f"Loan operation failed: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if own and conn is not None:
            conn.close()


def checkout(isbn, card_id, conn=None):
    """Check out one book; return the new loan as a one-element data list."""
    if not isinstance(isbn, str) or not isinstance(card_id, str) or not isbn.strip() or not card_id.strip():
        return _result(False, "Enter an ISBN and borrower ID.")
    isbn, card_id = isbn.strip(), card_id.strip()

    def operation(cur):
        # Lock the borrower and book so simultaneous checkouts cannot bypass limits.
        cur.execute("SELECT Card_id FROM BORROWER WHERE Card_id = %s FOR UPDATE", (card_id,))
        borrower = cur.fetchone()
        if borrower is None:
            raise LoanError("Borrower not found.")
        cur.execute("SELECT Isbn FROM BOOK WHERE Isbn = %s FOR UPDATE", (isbn,))
        book = cur.fetchone()
        if book is None:
            raise LoanError("Book not found.")
        cur.execute("SELECT Loan_id FROM BOOK_LOANS WHERE Isbn = %s AND Date_in IS NULL LIMIT 1", (isbn,))
        if cur.fetchone():
            raise LoanError("Book is not available; it is already checked out.")
        cur.execute("SELECT COUNT(*) AS total FROM BOOK_LOANS WHERE Card_id = %s AND Date_in IS NULL", (card_id,))
        if cur.fetchone()["total"] >= 3:
            raise LoanError("Borrower already has 3 active loans.")
        cur.execute("""SELECT f.Loan_id FROM FINES f JOIN BOOK_LOANS l ON l.Loan_id = f.Loan_id
                       WHERE l.Card_id = %s AND f.Paid = FALSE AND f.Fine_amt > 0 LIMIT 1""", (card_id,))
        if cur.fetchone():
            raise LoanError("Borrower has an unpaid fine.")
        today = date.today()
        due = today + timedelta(days=14)
        cur.execute("""INSERT INTO BOOK_LOANS (Isbn, Card_id, Date_out, Due_date, Date_in)
                       VALUES (%s, %s, %s, %s, NULL)""", (book['Isbn'], borrower['Card_id'], today, due))
        return ([{"loan_id": cur.lastrowid, "isbn": book['Isbn'], "card_id": borrower['Card_id'],
                  "date_out": today.isoformat(), "due_date": due.isoformat(), "date_in": None}], "Book checked out successfully.")
    return _write(operation, conn)


def search_loans(query, conn=None):
    """Search active loans by exact ISBN/card ID or case-insensitive name substring."""
    if not isinstance(query, str) or not query.strip():
        return _result(False, "Enter an ISBN, borrower ID or borrower name.")
    query = query.strip()
    pattern = '%' + query.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'
    own = conn is None
    cur = None
    try:
        conn = conn or get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("""SELECT l.Loan_id AS loan_id, l.Isbn AS isbn, b.Title AS title,
                              l.Card_id AS card_id, r.Bname AS bname, l.Date_out AS date_out,
                              l.Due_date AS due_date, l.Date_in AS date_in
                       FROM BOOK_LOANS l JOIN BOOK b ON b.Isbn = l.Isbn
                       JOIN BORROWER r ON r.Card_id = l.Card_id
                       WHERE l.Date_in IS NULL AND
                       (LOWER(l.Isbn) = LOWER(%s) OR LOWER(l.Card_id) = LOWER(%s)
                        OR LOWER(r.Bname) LIKE LOWER(%s) ESCAPE '!') ORDER BY l.Loan_id""",
                    (query, query, pattern))
        data = cur.fetchall()
        for row in data:
            for key in ('date_out', 'due_date'):
                row[key] = row[key].isoformat()
        return _result(True, f"{len(data)} active loan(s) found.", data)
    except Exception as exc:
        return _result(False, f"Loan search failed: {exc}")
    finally:
        if cur is not None:
            cur.close()
        if own and conn is not None:
            conn.close()


def checkin(loan_ids, conn=None):
    """Return 1–3 distinct active loan IDs atomically; preserve loan history."""
    if type(loan_ids) is int:
        loan_ids = [loan_ids]
    if (not isinstance(loan_ids, (list, tuple)) or not 1 <= len(loan_ids) <= 3
            or any(type(i) is not int or i <= 0 for i in loan_ids)
            or len(set(loan_ids)) != len(loan_ids)):
        return _result(False, "Select 1 to 3 distinct positive loan IDs.")
    ids = sorted(loan_ids)

    def operation(cur):
        today = date.today()
        data = []
        for loan_id in ids:
            cur.execute("SELECT Loan_id, Isbn, Card_id, Date_out, Due_date, Date_in FROM BOOK_LOANS WHERE Loan_id = %s FOR UPDATE", (loan_id,))
            row = cur.fetchone()
            if row is None:
                raise LoanError(f"Loan {loan_id} not found.")
            if row['Date_in'] is not None:
                raise LoanError(f"Loan {loan_id} has already been returned.")
            if today < row['Date_out']:
                raise LoanError(f"Loan {loan_id} has a future checkout date.")
            cur.execute("UPDATE BOOK_LOANS SET Date_in = %s WHERE Loan_id = %s", (today, loan_id))
            data.append({"loan_id": loan_id, "isbn": row['Isbn'], "card_id": row['Card_id'],
                         "date_out": row['Date_out'].isoformat(), "due_date": row['Due_date'].isoformat(),
                         "date_in": today.isoformat()})
        return data, f"{len(data)} book(s) checked in successfully."
    return _write(operation, conn)
