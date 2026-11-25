import unittest
from datetime import date

import mysql.connector

from database.database import get_connection, run_schema
from database.import_data import DATA, rows
from services.search import search_books

TEST_DB = "library_test"


def setUpModule():
    global conn
    boot = get_connection(database="mysql")
    boot.cursor().execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DB} CHARACTER SET utf8mb4")
    boot.close()
    conn = get_connection(database=TEST_DB)
    load_fixtures(conn)


def load_fixtures(conn):
    run_schema(conn)
    c = conn.cursor()
    c.executemany("INSERT INTO BOOK VALUES (%s,%s)", [
        ("0923398364", "Houses of Williamsburg, Virginia"),
        ("0891787631", "College Algebra"),
        ("T619875682", "Wills and Trusts for Retirement"),
        ("X2723786q6", "The History of the Han Dynasty"),
    ])
    c.executemany("INSERT INTO AUTHORS VALUES (%s,%s)", [
        (1, "John Smith"), (2, "Will McDaniels"), (3, "Mary Jones"),
        (4, "Barbara Brown, ESQ"), (5, "Dawn Williamson")])
    c.executemany("INSERT INTO BOOK_AUTHORS (Isbn, Author_id) VALUES (%s,%s)", [
        ("0923398364", 1), ("0891787631", 2), ("0891787631", 3),
        ("T619875682", 4), ("X2723786q6", 5)])
    c.execute("INSERT INTO BORROWER VALUES ('ID000001','111-11-1111','Test Person','1 Main St','555')")
    conn.commit()


def tearDownModule():
    conn.cursor().execute(f"DROP DATABASE {TEST_DB}")
    conn.close()


def isbns(q):
    r = search_books(q, conn)
    assert r["success"], r["message"]
    return [d["isbn"] for d in r["data"]]


class SearchTests(unittest.TestCase):
    def test_import_integrity(self):
        # real CSVs load with all foreign keys satisfied; loans/fines start empty
        from database.import_data import import_all
        conn.commit()  # release any open read transaction before DROP TABLE
        import_all(conn)
        cur = conn.cursor()
        counts = {}
        for t in ("BOOK", "AUTHORS", "BOOK_AUTHORS", "BORROWER", "BOOK_LOANS", "FINES"):
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            counts[t] = cur.fetchone()[0]
        self.assertEqual(counts["BOOK"], len(rows("books.csv", False)))
        self.assertEqual(counts["BOOK_AUTHORS"], len(rows("book_authors.csv", False)))
        self.assertEqual(counts["BORROWER"], len(rows("borrowers.csv", True)))
        self.assertEqual((counts["BOOK_LOANS"], counts["FINES"]), (0, 0))
        load_fixtures(conn)  # restore small fixtures for the other tests

    def test_partial_title_and_author_case_insensitive(self):
        self.assertCountEqual(isbns("WILL"), ["0923398364", "0891787631", "T619875682", "X2723786q6"])

    def test_multiple_authors_comma_separated_and_book_once(self):
        r = search_books("algebra", conn)["data"]
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["authors"], "Mary Jones, Will McDaniels")

    def test_combined_terms_narrow(self):
        self.assertEqual(isbns("will jones"), ["0891787631"])

    def test_exact_isbn_one_result(self):
        self.assertEqual(isbns("0891787631"), ["0891787631"])

    def test_no_match_and_empty_query(self):
        self.assertEqual(isbns("zzzzqq"), [])
        self.assertFalse(search_books("  ", conn)["success"])

    def test_wildcards_are_literal(self):
        self.assertEqual(isbns("%"), [])

    def test_checked_out_status(self):
        self.assertEqual(search_books("0891787631", conn)["data"][0]["status"], "IN")
        c = conn.cursor()
        c.execute("INSERT INTO BOOK_LOANS (Isbn, Card_id, Date_out, Due_date) VALUES ('0891787631','ID000001',%s,%s)",
                  (date.today(), date.today()))
        conn.commit()
        self.assertEqual(search_books("0891787631", conn)["data"][0]["status"], "OUT")
        c.execute("UPDATE BOOK_LOANS SET Date_in = CURDATE()")  # returned -> available again
        conn.commit()
        self.assertEqual(search_books("0891787631", conn)["data"][0]["status"], "IN")


if __name__ == "__main__":
    unittest.main()
