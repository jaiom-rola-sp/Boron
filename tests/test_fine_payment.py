import unittest 
from datetime import date 
from decimal import Decimal 
from unittest.mock import patch 

from services.fine_payment import get_fines, get_borrower_fines, pay_fines 


class FinePaymentTests(unittest.TestCase):
    
    def setUp(self):
       # using mock connections instead of changing the actual database
        self.connection_patch = patch("services.fine_payment.get_connection")
        self.refresh_patch = patch(
            "services.fine_payment.refresh_fines",
            return_value={
                "success": True,
                "message": "Fines refreshed successfully." 
            }         
        )  
                
        self.connection = self.connection_patch.start().return_value
        self.refresh = self.refresh_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.addCleanup(self.refresh_patch.stop) 
        self.cursor = self.connection.cursor.return_value 

    def test_grouped_unpaid_fines(self):
        self.cursor.fetchall.return_value = [  
            {                
                "card_id": "ID000001", 
                "borrower_name": "Alice", 
                "total_fines": Decimal("1.75"),
                "fine_count": 2           
            }    
        ]        
        
        result = get_fines()  
        self.assertTrue(result["success"]) 
        self.assertEqual(        
        result["data"][0]["total_fines"],   
        Decimal("1.75") 
        )  
        
        sql = self.cursor.execute.call_args.args[0]   
        self.assertIn("GROUP BY bl.Card_id", sql)     
        self.assertIn("WHERE f.Paid = FALSE", sql)   
        self.assertIn("unreturned_total", sql)
        self.assertIn("payable_total", sql)

    def test_include_paid_fines(self):     
        self.cursor.fetchall.return_value = []    
        result = get_fines(include_paid=True)   
        self.assertTrue(result["success"])   
        sql = self.cursor.execute.call_args.args[0] 
        self.assertNotIn("WHERE f.Paid = FALSE", sql) 

    def test_list_borrower_fines(self):     
        self.cursor.fetchall.return_value = [
            {               
                "loan_id": 11,            
                "isbn": "0002005018",       
                "fine_amount": Decimal("0.75"),  
                "paid": 0,   
                "date_in": date(2026, 11, 20)  
            }    
        ]
           
        result = get_borrower_fines("ID000001")        
        self.assertTrue(result["success"])      
        self.assertEqual(result["data"][0]["loan_id"], 11)
        self.assertEqual(          
        self.cursor.execute.call_args.args[1],
        ("ID000001",)      
        
        )     

    def test_full_payment(self):  
        self.cursor.fetchall.return_value = [ 
            {                
                "loan_id": 11,                
                "fine_amount": Decimal("0.50"),                
                "date_in": date(2026, 11, 20)             
            }, 
            {                 
                "loan_id": 12,                 
                "fine_amount": Decimal("1.25"),                
                "date_in": date(2026, 11, 21)            
            }     
        ]          
        result = pay_fines("ID000001")       
        self.assertTrue(result["success"], result["message"])  
        self.assertEqual(result["data"]["amount_paid"], "1.75")   
        self.assertEqual(result["data"]["fines_paid"], 2)     
        self.assertEqual(self.cursor.execute.call_count, 3)     
        self.connection.commit.assert_called_once()        
        self.refresh.assert_called_once()     

    def test_unreturned_book_blocks_payment(self):    
        self.cursor.fetchall.return_value = [            
            {               
                "loan_id": 11,          
                "fine_amount": Decimal("0.50"),   
                "date_in": date(2026, 11, 20)    
            },            
            {                
                "loan_id": 12,
                "fine_amount": Decimal("1.25"),                
                "date_in": None       
            }      
        ] 

        result = pay_fines("ID000001")        
        self.assertFalse(result["success"])        
        self.assertEqual(self.cursor.execute.call_count, 1)        
        self.connection.rollback.assert_called_once()         
        self.connection.commit.assert_not_called()      
    
    def test_no_unpaid_fines(self):         
        self.cursor.fetchall.return_value = []         
        result = pay_fines("ID000001")          
        self.assertFalse(result["success"])         
        self.connection.commit.assert_not_called()     

    def test_failed_refresh_blocks_payment(self):         
        self.refresh.return_value = {             
            "success": False,             
            "message": "Refresh failed"     
        }    

        result = pay_fines("ID000001")          
        self.assertFalse(result["success"])         
        self.assertIn("Refresh failed", result["message"])         
        self.connection.start_transaction.assert_not_called()     

    def test_update_error_rolls_back(self):         
        self.cursor.fetchall.return_value = [             
            {
                "loan_id": 11,                
                "fine_amount": Decimal("0.50"),                 
                "date_in": date(2026, 11, 20)          
            }       
        ]
    
        self.cursor.execute.side_effect = [        
            None,
            RuntimeError("Database error")      
        ]  
    
        result = pay_fines("ID000001")         
        self.assertFalse(result["success"])         
        self.connection.rollback.assert_called_once()        
        self.connection.commit.assert_not_called()      
               
    def test_invalid_card_id(self):         
        self.assertFalse(pay_fines("")["success"])       
        self.assertFalse(get_borrower_fines(None)["success"]) 
        self.connection.start_transaction.assert_not_called() 
             
if __name__ == "__main__":
    unittest.main()
