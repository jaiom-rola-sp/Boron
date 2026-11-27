from decimal import Decimal

from database.database import get_connection
from services.fine_calculator import refresh_fines

#get total fines for each borrower
def get_fines(include_paid=False):
    connection = None;
    cursor = None;

    try:
        connection = get_connection() 
        cursor = connection.cursor(dictionary=True)

        query = """
           SELECT bl.Card_id AS card_id,
                  b.Bname AS borrower_name,
                  SUM(f.Fine_amt) AS total_fines,
                  COUNT(*) AS fine_count,
                  SUM(IF(f.Paid = FALSE AND bl.Date_in IS NOT NULL, f.Fine_amt, 0)) AS payable_total,
                  SUM(IF(f.Paid = FALSE AND bl.Date_in IS NULL, f.Fine_amt, 0)) AS unreturned_total,
                  SUM(IF(f.Paid = FALSE AND bl.Date_in IS NULL, 1, 0)) AS unreturned_count
           FROM FINES AS f
           JOIN BOOK_LOANS AS bl ON f.Loan_id = bl.Loan_id
           JOIN BORROWER AS b ON bl.Card_id = b.Card_id
        """

        # show only unpaid fines unless the paid fines are requested
        if not include_paid:
            query += " WHERE f.Paid = FALSE"    

        query += " GROUP BY bl.Card_id, b.Bname ORDER BY bl.Card_id"

        cursor.execute(query)
        rows = cursor.fetchall()    

        return {
            "success": True,
            "message": "Fines retrieved.",
            "data": rows
        }
    except Exception as error:
        return {
            "success": False,
            "message": f"Could not retrieve fines: {error}",
            "data": []
        }
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


# get all fine records for 1 borrower 
def get_borrower_fines(card_id):
    if not isinstance(card_id, str) or not card_id.strip():
        return {
            "success": False,
            "message": "Borrower card ID is required.",
            "data": []
        } 
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
           SELECT f.Loan_id AS loan_id,
                  bl.Isbn AS isbn,
                  f.Fine_amt AS fine_amount,
                  f.Paid AS paid,
                  bl.Date_in AS date_in
           FROM FINES AS f
           JOIN BOOK_LOANS AS bl ON f.Loan_id = bl.Loan_id
           WHERE bl.Card_id = %s
           ORDER BY f.Paid, f.Loan_id
        """, (card_id.strip(),))

        return {
            "success": True,
            "message": "Borrower fines retrieved.",
            "data": cursor.fetchall()
        }

    except Exception as error:
        return {
            "success": False,
            "message": f"Could not retrieve borrower fines: {error}",
            "data": []
        }

    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()

# pay the full unpaid balance for 1 borrorwer 
def pay_fines(card_id):
    if not isinstance(card_id, str) or not card_id.strip():      
        return {
            "success": False,
            "message": "Borrower card ID is required.",
            "data": None
        }

    connection = None
    cursor = None

    try:
        refresh_result = refresh_fines()

        if not refresh_result["success"]:
            return {
                "success": False,
                "message": refresh_result["message"],
                "data": None
            }

        connection = get_connection()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)

        # find all unpaid fines belonging to 1 owner and lock them
        cursor.execute("""
            SELECT f.Loan_id AS loan_id,
                   f.Fine_amt AS fine_amount,
                   bl.Date_in AS date_in
            FROM FINES AS f
            JOIN BOOK_LOANS AS bl ON f.Loan_id = bl.Loan_id
            WHERE bl.Card_id = %s AND f.Paid = FALSE
            FOR UPDATE
        """, (card_id.strip(),))

        fines = cursor.fetchall()

        if not fines:
            connection.rollback()   
            return {
                "success": False,
                "message": "No unpaid fines for this borrower.",
                "data": None
            }  

        for fine in fines:
            if fine["date_in"] is None:
                connection.rollback()
                return {
                    "success": False,
                    "message": "Return all fined books before paying the balance.",
                    "data": None
                } 

        total = Decimal("0.00")

        # mark all unpaid fines as paid in 1 transaction
        for fine in fines:
            total += fine["fine_amount"]

            cursor.execute("""
                UPDATE FINES SET Paid = TRUE
                WHERE Loan_id = %s AND Paid = FALSE
            """, (fine["loan_id"],))

        connection.commit()

        return { 
            "success": True,
            "message": "All unpaid fines paid.", 
            "data": {
                "card_id": card_id.strip(),
                "amount_paid": str(total),
                "fines_paid": len(fines)
            }
        }
    
    except Exception as error:
        if connection is not None:
            connection.rollback()
            
        return {
            "success": False,
            "message": f"Payment failed: {error}",
            "data": None
        } 
        
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()           

