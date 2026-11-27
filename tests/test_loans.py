import unittest
from datetime import date, timedelta
from uuid import uuid4
from database.database import get_connection, run_schema
from services.loans import checkout, search_loans, checkin
from services.search import search_books


class LoanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = 'library_loans_test_' + uuid4().hex[:12]
        boot = get_connection(database='mysql')
        try:
            cur = boot.cursor()
            cur.execute(f'CREATE DATABASE `{cls.db}` CHARACTER SET utf8mb4')
            cur.close()
        finally:
            boot.close()
        cls.addClassCleanup(cls.drop_database)

    @classmethod
    def drop_database(cls):
        boot = get_connection(database='mysql')
        try:
            cur = boot.cursor()
            cur.execute(f'DROP DATABASE `{cls.db}`')
            cur.close()
        finally:
            boot.close()

    def setUp(self):
        self.conn = get_connection(database=self.db)
        self.addCleanup(self.conn.close)
        run_schema(self.conn)
        cur = self.conn.cursor()
        self.books = [f'{i:010d}' for i in range(1, 6)]
        cur.executemany('INSERT INTO BOOK VALUES (%s,%s)', [(i, 'Test Book '+i) for i in self.books])
        cur.executemany('INSERT INTO BORROWER VALUES (%s,%s,%s,%s,%s)', [
            ('ID000001','111-11-1111','Test Alice','Test address','555'),
            ('ID000002','222-22-2222','Test Bob','Test address','555')])
        self.conn.commit()
        cur.close()

    def out(self, n=0, card='ID000001'):
        result = checkout(self.books[n], card, self.conn)
        self.assertTrue(result['success'], result['message'])
        return result['data'][0]

    def find(self, query):
        result = search_loans(query, self.conn)
        self.conn.rollback()  # end the read transaction before the next write
        self.assertTrue(result['success'], result['message'])
        return result['data']

    def test_checkout_due_date(self):
        loan = self.out()
        self.assertEqual(loan['date_out'], date.today().isoformat())
        self.assertEqual(loan['due_date'], (date.today()+timedelta(days=14)).isoformat())
        self.assertIsNone(loan['date_in'])
        self.assertEqual(self.find(self.books[0])[0]['loan_id'], loan['loan_id'])

    def test_unknown_ids(self):
        self.assertFalse(checkout('missing','ID000001',self.conn)['success'])
        self.assertFalse(checkout(self.books[0],'missing',self.conn)['success'])
        self.assertFalse(checkout('', 'ID000001', self.conn)['success'])

    def test_duplicate_checkout(self):
        self.out()
        for card in ('ID000001','ID000002'):
            self.assertIn('not available', checkout(self.books[0],card,self.conn)['message'])

    def test_three_loan_limit_and_return(self):
        loans = [self.out(i) for i in range(3)]
        self.assertIn('3 active', checkout(self.books[3],'ID000001',self.conn)['message'])
        self.assertTrue(checkin(loans[0]['loan_id'],self.conn)['success'])
        self.out(3)

    def test_unpaid_and_paid_fine(self):
        loan = self.out()
        cur = self.conn.cursor()
        # make the loan genuinely 6 days late so refresh_fines keeps the $1.50 fine
        cur.execute('UPDATE BOOK_LOANS SET Date_out=%s, Due_date=%s WHERE Loan_id=%s',
                    (date.today()-timedelta(days=20), date.today()-timedelta(days=6), loan['loan_id']))
        self.conn.commit()
        self.assertTrue(checkin(loan['loan_id'],self.conn)['success'])
        cur.execute('INSERT INTO FINES VALUES (%s, 1.50, FALSE)', (loan['loan_id'],))
        self.conn.commit()
        self.assertIn('unpaid fine', checkout(self.books[1],'ID000001',self.conn)['message'])
        self.out(2,'ID000002')
        cur.execute('UPDATE FINES SET Paid=TRUE WHERE Loan_id=%s', (loan['loan_id'],))
        self.conn.commit()
        self.out(1)
        cur.close()

    def test_late_book_still_out_blocks_checkout_without_manual_refresh(self):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO BOOK_LOANS (Isbn, Card_id, Date_out, Due_date) VALUES (%s,'ID000001',%s,%s)",
                    (self.books[0], date.today()-timedelta(days=20), date.today()-timedelta(days=6)))
        self.conn.commit()
        cur.close()
        self.assertIn('unpaid fine', checkout(self.books[1], 'ID000001', self.conn)['message'])
        self.out(1, 'ID000002')  # other borrowers are unaffected

    def test_search_and_batch_return(self):
        loans = [self.out(i) for i in range(3)]
        self.assertEqual(len(self.find('ID000001')),3)
        self.assertEqual(len(self.find('aLiCe')),3)
        self.assertEqual(len(self.find(self.books[0])),1)
        self.assertEqual(self.find('%'),[])
        self.assertEqual(self.find('Bob'),[])
        result = checkin([l['loan_id'] for l in loans],self.conn)
        self.assertTrue(result['success'],result['message'])
        self.assertEqual(len(result['data']),3)
        self.assertTrue(all(l['date_in']==date.today().isoformat() for l in result['data']))
        self.assertEqual(self.find('Alice'),[])
        cur = self.conn.cursor()
        cur.execute('SELECT COUNT(*) FROM BOOK_LOANS WHERE Date_in IS NOT NULL')
        self.assertEqual(cur.fetchone()[0],3)
        cur.close()

    def test_search_combined_terms(self):
        self.out(0); self.out(1); self.out(2, 'ID000002')
        self.assertEqual(len(self.find('ID000001 ' + self.books[0])), 1)   # card + isbn
        self.assertEqual(len(self.find('alice ' + self.books[1])), 1)      # name + isbn
        self.assertEqual(len(self.find('test alice')), 2)                  # two name words
        self.assertEqual(self.find('ID000002 ' + self.books[0]), [])       # mismatched pair
        self.assertEqual(len(self.find('Test Bob')), 1)                    # name containing a space

    def test_invalid_batch_rolls_back(self):
        loan = self.out()['loan_id']
        for ids in ([], [loan,loan], [1,2,3,4], [loan,999999], ['1']):
            self.assertFalse(checkin(ids,self.conn)['success'])
        self.assertEqual(len(self.find('Alice')),1)
        self.assertTrue(checkin(loan,self.conn)['success'])
        self.assertFalse(checkin(loan,self.conn)['success'])

    def test_search_service_integration(self):
        def status():
            r = search_books(self.books[0],self.conn)
            self.conn.rollback()
            self.assertTrue(r['success'],r['message'])
            return r['data'][0]['status']
        self.assertEqual(status(),'IN')
        loan = self.out()
        self.assertEqual(status(),'OUT')
        self.assertTrue(checkin(loan['loan_id'],self.conn)['success'])
        self.assertEqual(status(),'IN')
        self.out(0,'ID000002')


if __name__ == '__main__':
    unittest.main()
