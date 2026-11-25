from database.database import get_connection


def _like(term):
    # escape LIKE wildcards so "50%" or "a_b" match literally
    return "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def search_books(query, conn=None):
    """Case-insensitive substring search over ISBN, title and author names.

    Every whitespace-separated term must match at least one of the three fields,
    so "will jones" finds books matching both. Returns {success, message, data};
    data rows: {isbn, title, authors (comma-separated), available (bool), status ("IN"/"OUT")}.
    """
    terms = (query or "").split()
    if not terms:
        return {"success": False, "message": "Enter a search term.", "data": []}

    # shortcut: default MySQL collation is case-insensitive; a case-sensitive DB would break this
    cond = """(b.Isbn LIKE %s OR b.Title LIKE %s OR EXISTS (
                 SELECT 1 FROM BOOK_AUTHORS x JOIN AUTHORS y ON y.Author_id = x.Author_id
                 WHERE x.Isbn = b.Isbn AND y.Name LIKE %s))"""
    sql = f"""
        SELECT b.Isbn, b.Title,
               (SELECT GROUP_CONCAT(a.Name ORDER BY a.Name SEPARATOR ', ')
                  FROM BOOK_AUTHORS ba JOIN AUTHORS a ON a.Author_id = ba.Author_id
                 WHERE ba.Isbn = b.Isbn) AS authors,
               NOT EXISTS (SELECT 1 FROM BOOK_LOANS l
                            WHERE l.Isbn = b.Isbn AND l.Date_in IS NULL) AS available
          FROM BOOK b
         WHERE {' AND '.join([cond] * len(terms))}
         ORDER BY b.Title, b.Isbn"""
    params = [_like(t) for t in terms for _ in range(3)]

    own = conn is None
    try:
        conn = conn or get_connection()
        cur = conn.cursor()
        cur.execute(sql, params)
        data = [{"isbn": i, "title": t, "authors": a or "", "available": bool(av),
                 "status": "IN" if av else "OUT"} for i, t, a, av in cur.fetchall()]
        cur.close()
    except Exception as e:
        return {"success": False, "message": f"Search failed: {e}", "data": []}
    finally:
        if own and conn:
            conn.close()
    return {"success": True, "message": f"{len(data)} result(s).", "data": data}
