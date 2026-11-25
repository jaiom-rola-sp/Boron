import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def get_connection(database=None):
    """Open a MySQL connection using .env settings. database=None uses DB_NAME."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=database or os.getenv("DB_NAME", "library"),
    )


def run_schema(conn):
    """(Re)create all six tables from schema.sql. Destroys existing data."""
    sql = (Path(__file__).parent / "schema.sql").read_text()
    cur = conn.cursor()
    # schema.sql has no ';' inside statements, so a plain split is safe
    for stmt in filter(None, (s.strip() for s in sql.split(";"))):
        cur.execute(stmt)
    conn.commit()
    cur.close()
