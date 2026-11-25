"""Create the database, apply schema.sql and load the four CSVs. Loans/fines stay empty.

Run from the repo root:  python -m database.import_data
"""
import csv
import os

import mysql.connector

from database.database import ROOT, get_connection, run_schema

DATA = ROOT / "data"


def rows(name, header):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        if header:
            next(r)
        return list(r)


def load(conn, sql, data):
    cur = conn.cursor()
    cur.executemany(sql, data)
    cur.close()


def import_all(conn):
    run_schema(conn)
    # order matters: parents before children (foreign keys)
    load(conn, "INSERT INTO BOOK (Isbn, Title) VALUES (%s, %s)", rows("books.csv", False))
    load(conn, "INSERT INTO AUTHORS (Author_id, Name) VALUES (%s, %s)", rows("authors.csv", False))
    load(conn, "INSERT INTO BOOK_AUTHORS (Isbn, Author_id) VALUES (%s, %s)", rows("book_authors.csv", False))
    load(conn, "INSERT INTO BORROWER (Card_id, Ssn, Bname, Address, Phone) VALUES (%s, %s, %s, %s, %s)",
         rows("borrowers.csv", True))
    conn.commit()


if __name__ == "__main__":
    db = os.getenv("DB_NAME", "library")
    # connect without a database first so we can create it
    boot = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"), password=os.getenv("DB_PASSWORD", ""))
    boot.cursor().execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4")
    boot.close()
    conn = get_connection()
    import_all(conn)
    cur = conn.cursor()
    for t in ("BOOK", "AUTHORS", "BOOK_AUTHORS", "BORROWER", "BOOK_LOANS", "FINES"):
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"{t}: {cur.fetchone()[0]}")
    conn.close()
