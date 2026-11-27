"""Run from the project root: python -m unittest discover -s tests -v."""

import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from services import fine_calculator as fines


class CalculationTests(unittest.TestCase):
    def test_returned_before_due_date(self):
        self.assertEqual(fines.calculate_fine("2026-11-10", "2026-11-09"), Decimal("0.00"))

    def test_returned_on_due_date(self):
        self.assertEqual(fines.calculate_fine("2026-11-10", "2026-11-10"), Decimal("0.00"))

    def test_returned_four_days_late(self):
        self.assertEqual(fines.calculate_fine("2026-11-10", "2026-11-14"), Decimal("1.00"))

    def test_outstanding_overdue_book(self):
        self.assertEqual(fines.calculate_fine(date.today() - timedelta(days=3)), Decimal("0.75"))

    def test_outstanding_book_not_due(self):
        self.assertEqual(fines.calculate_fine(date.today() + timedelta(days=3)), Decimal("0.00"))

    def test_calendar_days_across_leap_day(self):
        self.assertEqual(fines.calculate_fine("2024-02-28", "2024-03-01"), Decimal("0.50"))

    def test_fixed_decimal_result(self):
        amount = fines.calculate_fine("2026-11-10", "2026-11-11")
        self.assertIsInstance(amount, Decimal)
        self.assertEqual(str(amount), "0.25")


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.connection = Mock()
        self.cursor = self.connection.cursor.return_value
        self.connection_patch = patch.object(fines, "get_connection", return_value=self.connection)
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)

    def loan(self, amount=None, paid=None, returned=None, days_late=4):
        return {"Loan_id": 7, "Due_date": date.today() - timedelta(days=days_late),
                "Date_in": returned, "Fine_amt": amount, "Paid": paid}

    def test_inserts_missing_overdue_fine(self):
        self.cursor.fetchall.return_value = [self.loan()]
        result = fines.refresh_fines()
        self.assertTrue(result["success"])
        self.assertEqual(result["data"], {"inserted": 1, "updated": 0})
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("INSERT INTO FINES", sql)
        self.assertEqual(params, (7, Decimal("1.00")))
        self.connection.commit.assert_called_once()

    def test_updates_existing_unpaid_fine(self):
        self.cursor.fetchall.return_value = [self.loan(Decimal("0.25"), False)]
        result = fines.refresh_fines()
        self.assertEqual(result["data"], {"inserted": 0, "updated": 1})
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("UPDATE FINES", sql)
        self.assertIn("Paid = FALSE", sql)
        self.assertEqual(params, (Decimal("1.00"), 7))

    def test_repeated_refresh_leaves_same_fine_unchanged(self):
        self.cursor.fetchall.return_value = [self.loan(Decimal("1.00"), False)]
        for _ in range(2):
            self.assertEqual(fines.refresh_fines()["data"], {"inserted": 0, "updated": 0})
        # Only the two SELECTs; no INSERT or UPDATE.
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_paid_fine_never_changes(self):
        self.cursor.fetchall.return_value = [self.loan(Decimal("0.25"), True)]
        self.assertTrue(fines.refresh_fines()["success"])
        self.assertEqual(self.cursor.execute.call_count, 1)

    def test_no_fine_for_book_not_overdue(self):
        self.cursor.fetchall.return_value = [self.loan(days_late=-2)]
        fines.refresh_fines()
        self.assertEqual(self.cursor.execute.call_count, 1)

    def test_return_date_stops_fine_accrual(self):
        returned = date.today() - timedelta(days=2)
        self.cursor.fetchall.return_value = [self.loan(returned=returned)]
        fines.refresh_fines()
        self.assertEqual(self.cursor.execute.call_args.args[1], (7, Decimal("0.50")))

    def test_error_rolls_back_and_closes_connection(self):
        self.cursor.fetchall.return_value = [self.loan()]
        self.cursor.execute.side_effect = [None, RuntimeError("write failed")]
        result = fines.refresh_fines()
        self.assertFalse(result["success"])
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.cursor.close.assert_called_once()
        self.connection.close.assert_called_once()


class UnpaidCheckTests(unittest.TestCase):
    @patch.object(fines, "get_connection")
    @patch.object(fines, "refresh_fines", return_value={"success": True})
    def test_unpaid_result_and_borrower_filter(self, refresh, connect):
        cursor = connect.return_value.cursor.return_value
        for value in (0, 1):
            cursor.fetchone.return_value = (value,)
            self.assertEqual(fines.has_unpaid_fines("ID000001"), bool(value))
        sql, params = cursor.execute.call_args.args
        self.assertIn("bl.Card_id = %s", sql)
        self.assertEqual(params, ("ID000001",))
        self.assertEqual(refresh.call_count, 2)

    @patch.object(fines, "get_connection")
    @patch.object(fines, "refresh_fines", return_value={"success": False, "message": "DB unavailable"})
    def test_refresh_failure_does_not_report_clear_balance(self, refresh, connect):
        with self.assertRaises(RuntimeError):
            fines.has_unpaid_fines("ID000001")
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
