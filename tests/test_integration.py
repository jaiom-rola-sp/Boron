"""End-to-end flow across every service, on a throwaway database."""
import os
import unittest
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from database.database import get_connection, run_schema
from services.borrowers import create_borrower
from services.fine_calculator import has_unpaid_fines, refresh_fines
from services.fine_payment import get_borrower_fines, pay_fines
from services.loans import checkin, checkout, search_loans
from services.search import search_books


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.db = "library_e2e_" + uuid4().hex[:10]
        boot = get_connection(database="mysql")
        boot.cursor().execute(f"CREATE DATABASE `{self.db}` CHARACTER SET utf8mb4")
        boot.close()
        self.addCleanup(self.drop)
        # services open their own connections via get_connection(), which reads DB_NAME
        old = os.environ.get("DB_NAME")
        os.environ["DB_NAME"] = self.db
        self.addCleanup(lambda: os.environ.__setitem__("DB_NAME", old) if old else os.environ.pop("DB_NAME"))
        conn = get_connection()
        run_schema(conn)
        conn.cursor().executemany("INSERT INTO BOOK VALUES (%s,%s)",
                                  [("0000000001", "Book One"), ("0000000002", "Book Two")])
        conn.commit()
        conn.close()

    def drop(self):
        boot = get_connection(database="mysql")
        boot.cursor().execute(f"DROP DATABASE `{self.db}`")
        boot.close()

    def sql(self, q, args=()):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(q, args)
        conn.commit()
        conn.close()

    def test_full_flow(self):
        b = create_borrower("Test Person", "123-45-6789", "1 Main St", "555")
        self.assertTrue(b["success"], b["message"])
        card = b["data"]["card_id"]
        self.assertFalse(create_borrower("Dup", "123456789", "2 Main St")["success"])  # one card per SSN

        self.assertEqual(search_books("book one")["data"][0]["status"], "IN")
        loan = checkout("0000000001", card)
        self.assertTrue(loan["success"], loan["message"])
        self.assertEqual(search_books("book one")["data"][0]["status"], "OUT")
        self.assertEqual(len(search_loans("test person")["data"]), 1)

        # book becomes 6 days late and is still out
        loan_id = loan["data"][0]["loan_id"]
        self.sql("UPDATE BOOK_LOANS SET Date_out=%s, Due_date=%s WHERE Loan_id=%s",
                 (date.today() - timedelta(days=20), date.today() - timedelta(days=6), loan_id))
        self.assertTrue(refresh_fines()["success"])
        self.assertTrue(has_unpaid_fines(card))
        self.assertEqual(get_borrower_fines(card)["data"][0]["fine_amount"], Decimal("1.50"))
        self.assertIn("unpaid fine", checkout("0000000002", card)["message"])
        self.assertFalse(pay_fines(card)["success"])  # book not returned yet

        self.assertTrue(checkin([loan_id])["success"])
        paid = pay_fines(card)
        self.assertTrue(paid["success"], paid["message"])
        self.assertEqual(paid["data"]["amount_paid"], "1.50")
        self.assertFalse(has_unpaid_fines(card))
        self.assertTrue(checkout("0000000002", card)["success"])  # allowed again


if __name__ == "__main__":
    unittest.main()
