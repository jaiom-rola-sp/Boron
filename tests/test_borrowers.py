import random
import unittest

from database.database import get_connection
from services.borrowers import create_borrower, generate_card_id


def _rand_ssn():
    return "9%02d-%02d-%04d" % (random.randint(0, 99), random.randint(0, 99), random.randint(0, 9999))


class TestBorrowers(unittest.TestCase):
    created = []

    @classmethod
    def tearDownClass(cls):
        conn = get_connection()
        cur = conn.cursor()
        for cid in cls.created:
            cur.execute("DELETE FROM BORROWER WHERE Card_id = %s", (cid,))
        conn.commit()
        conn.close()

    def _make(self, **kw):
        args = dict(name="Test User", ssn=_rand_ssn(), address="1 Main St", phone="555-0100")
        args.update(kw)
        r = create_borrower(**args)
        if r["success"]:
            self.created.append(r["data"]["card_id"])
        return r, args

    def test_missing_fields(self):
        for field in ("name", "ssn", "address"):
            r, _ = self._make(**{field: ""})
            self.assertFalse(r["success"])
            self.assertIn("Missing", r["message"])

    def test_bad_ssn(self):
        r, _ = self._make(ssn="123")
        self.assertFalse(r["success"])

    def test_success_and_duplicate_ssn(self):
        r, args = self._make()
        self.assertTrue(r["success"])
        dup, _ = self._make(ssn=args["ssn"].replace("-", ""))  # same SSN, different format
        self.assertFalse(dup["success"])
        self.assertIn("SSN", dup["message"])

    def test_unique_incrementing_ids(self):
        a, _ = self._make()
        b, _ = self._make()
        self.assertNotEqual(a["data"]["card_id"], b["data"]["card_id"])

    def test_id_format_matches_existing(self):
        r, _ = self._make()
        nxt = generate_card_id()
        cid = r["data"]["card_id"]
        self.assertEqual(len(nxt), len(cid))
        self.assertEqual(nxt.rstrip("0123456789"), cid.rstrip("0123456789"))


if __name__ == "__main__":
    unittest.main()
