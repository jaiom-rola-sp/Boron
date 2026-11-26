"""Fine calculation and refresh for the shared MySQL library schema."""

from datetime import date, datetime
from decimal import Decimal

DAILY_RATE = Decimal("0.25")


def get_connection():
    # Import only when needed so calculation can run without MySQL installed.
    from database.database import get_connection as connect
    return connect()


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def calculate_fine(due_date, date_in=None):
    """Return a Decimal fine; dates may be date objects or YYYY-MM-DD strings."""
    end_date = date.today() if date_in is None else _as_date(date_in)
    overdue_days = max(0, (end_date - _as_date(due_date)).days)
    return (DAILY_RATE * overdue_days).quantize(Decimal("0.01"))


def refresh_fines():
    """Refresh unpaid fines atomically; return success, message and data fields."""
    conn = None
    cursor = None
    try:
        conn = get_connection()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)
        # Locks prevent a check-in/payment from changing a selected record mid-refresh.
        cursor.execute("""
            SELECT bl.Loan_id, bl.Due_date, bl.Date_in, f.Fine_amt, f.Paid
            FROM BOOK_LOANS AS bl
            LEFT JOIN FINES AS f ON f.Loan_id = bl.Loan_id
            FOR UPDATE
        """)
        loans = cursor.fetchall()
        today = date.today()
        inserted = 0
        updated = 0

        for loan in loans:
            if loan["Paid"]:
                continue
            end_date = loan["Date_in"] if loan["Date_in"] is not None else today
            amount = calculate_fine(loan["Due_date"], end_date)

            if loan["Fine_amt"] is None:
                if amount > Decimal("0.00"):
                    cursor.execute("""
                        INSERT INTO FINES (Loan_id, Fine_amt, Paid)
                        VALUES (%s, %s, FALSE)
                        ON DUPLICATE KEY UPDATE
                            Fine_amt = IF(Paid = FALSE, VALUES(Fine_amt), Fine_amt)
                    """, (loan["Loan_id"], amount))
                    inserted += 1
            elif loan["Fine_amt"] != amount:
                cursor.execute("""
                    UPDATE FINES SET Fine_amt = %s
                    WHERE Loan_id = %s AND Paid = FALSE
                """, (amount, loan["Loan_id"]))
                updated += 1

        conn.commit()
        return {
            "success": True,
            "message": "Fines refreshed successfully.",
            "data": {"inserted": inserted, "updated": updated},
        }
    except Exception as error:
        if conn is not None:
            conn.rollback()
        return {"success": False, "message": f"Could not refresh fines: {error}", "data": None}
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


def has_unpaid_fines(card_id):
    """Return a bool for checkout; raise on DB failure so checkout cannot proceed."""
    result = refresh_fines()
    if not result["success"]:
        raise RuntimeError(result["message"])

    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM FINES AS f
                JOIN BOOK_LOANS AS bl ON bl.Loan_id = f.Loan_id
                WHERE bl.Card_id = %s AND f.Paid = FALSE AND f.Fine_amt > 0
            )
        """, (card_id,))
        return bool(cursor.fetchone()[0])
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()
