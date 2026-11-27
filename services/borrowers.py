"""Borrower management (Member 3).

Functions return {"success": bool, "message": str, "data": ...}.
No input()/print() here -- UI code lives in main.py.
"""
import re

from mysql.connector import IntegrityError

from database.database import get_connection

# Table/column names from the shared schema -- change here if Member 1 differs.
TABLE, CARD, NAME, SSN, ADDR, PHONE = "BORROWER", "Card_id", "Bname", "Ssn", "Address", "Phone"

DEFAULT_PREFIX, DEFAULT_WIDTH = "ID", 6   # used only if the table is empty
MAX_ATTEMPTS = 5


def _result(success, message, data=None):
    return {"success": success, "message": message, "data": data}


def _digits(s):
    return re.sub(r"\D", "", s or "")


def _clean(v):
    return v.strip() if isinstance(v, str) else v


def _next_card_id(cur):
    """Next ID in the same format as existing ones (prefix + zero-padded number)."""
    cur.execute(f"SELECT {CARD} FROM {TABLE}")
    best = None  # (number, prefix, width)
    for (cid,) in cur.fetchall():
        m = re.fullmatch(r"(\D*)(\d+)", str(cid).strip())
        if m:
            n = int(m.group(2))
            if best is None or n > best[0]:
                best = (n, m.group(1), len(m.group(2)))
    if best is None:
        return f"{DEFAULT_PREFIX}{1:0{DEFAULT_WIDTH}d}"
    n, prefix, width = best
    return f"{prefix}{n + 1:0{width}d}"


def generate_card_id():
    """Return the next unused card ID (e.g. 'ID000124'). Raises on DB error."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        return _next_card_id(cur)
    finally:
        conn.close()


def _ssn_exists(cur, ssn_digits):
    cur.execute(
        f"SELECT 1 FROM {TABLE} "
        f"WHERE REPLACE(REPLACE({SSN}, '-', ''), ' ', '') = %s LIMIT 1",
        (ssn_digits,),
    )
    return cur.fetchone() is not None


def _store_format(cur, ssn_digits):
    """Match existing SSN style (dashes or not) so data stays consistent."""
    cur.execute(f"SELECT {SSN} FROM {TABLE} LIMIT 1")
    row = cur.fetchone()
    if row and "-" in str(row[0]):
        return f"{ssn_digits[:3]}-{ssn_digits[3:5]}-{ssn_digits[5:]}"
    return ssn_digits


def create_borrower(name, ssn, address, phone=None):
    name, ssn, address, phone = _clean(name), _clean(ssn), _clean(address), _clean(phone)

    missing = [f for f, v in (("name", name), ("SSN", ssn), ("address", address)) if not v]
    if missing:
        return _result(False, f"Missing required field(s): {', '.join(missing)}.")

    ssn_digits = _digits(ssn)
    if len(ssn_digits) != 9:
        return _result(False, "SSN must contain exactly 9 digits (e.g. 123-45-6789).")

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        for _ in range(MAX_ATTEMPTS):
            if _ssn_exists(cur, ssn_digits):
                return _result(
                    False,
                    "A borrower with this SSN already exists; "
                    "each person may hold only one library card.",
                )

            card_id = _next_card_id(cur)
            try:
                cur.execute(
                    f"INSERT INTO {TABLE} ({CARD}, {SSN}, {NAME}, {ADDR}, {PHONE}) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (card_id, _store_format(cur, ssn_digits), name, address, phone or None),
                )
                conn.commit()
                return _result(True, f"Borrower created with card ID {card_id}.", {"card_id": card_id})
            except IntegrityError:
                conn.rollback()  # SSN taken or card-ID race -> loop re-checks both

        return _result(False, "Could not generate a unique card ID; please try again.")
    except Exception as e:  # DB down, schema mismatch, etc.
        if conn:
            conn.rollback()
        return _result(False, f"Database error: {e}")
    finally:
        if conn:
            conn.close()
