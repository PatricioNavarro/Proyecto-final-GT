"""Pruebas unitarias/integración de reglas de negocio. Ejecutar: python -m unittest discover -s tests -v"""
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from core import Library, DomainError

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.clock=[datetime(2026,11,19,10,0,tzinfo=ZoneInfo('America/Argentina/Buenos_Aires'))]
        self.db=Library(str(Path(self.temp.name)/'test.sqlite3'),now=lambda:self.clock[0])
        self.db.ensure_seed('ClaveAdminSegura!',demo=True)
        with self.db.transaction() as con:
            self.admin=dict(con.execute("SELECT id,name,email,role FROM users WHERE role='admin'").fetchone())
            self.ana=dict(con.execute("SELECT id,name,email,role FROM users WHERE email='ana@bibliolab.test'").fetchone())
            self.bruno=dict(con.execute("SELECT id,name,email,role FROM users WHERE email='bruno@bibliolab.test'").fetchone())
            self.one=con.execute("SELECT id FROM books WHERE title='Ficciones'").fetchone()['id']
            self.multi=con.execute("SELECT id FROM books WHERE title='Introducción a Python'").fetchone()['id']

    def tearDown(self): self.temp.cleanup()
    def assertCode(self,code,fn,*args):
        with self.assertRaises(DomainError) as cm:fn(*args)
        self.assertEqual(cm.exception.status,code)

    def test_seed_has_catalog_and_users(self):
        self.assertEqual(len(self.db.books()),6)
        self.assertEqual(len(self.db.students(self.admin)),2)

    def test_login_and_session_logout(self):
        token,u=self.db.login('ana@bibliolab.test','Alumno2026!')
        self.assertEqual(u['id'],self.ana['id'])
        self.assertEqual(self.db.authenticate(token)['role'],'student')
        self.db.logout(token)
        self.assertCode(401,self.db.authenticate,token)

    def test_invalid_login(self):
        self.assertCode(401,self.db.login,'ana@bibliolab.test','mal')

    def test_first_reservation_ready_and_next_waiting(self):
        a=self.db.reserve(self.ana,self.one)
        b=self.db.reserve(self.bruno,self.one)
        self.assertEqual(a['status'],'ready')
        self.assertEqual(b['status'],'waiting')
        self.assertEqual(self.db.books('Ficciones')[0]['available'],0)

    def test_duplicate_reservation_rejected(self):
        self.db.reserve(self.ana,self.one)
        self.assertCode(409,self.db.reserve,self.ana,self.one)

    def test_cancel_promotes_next_in_queue(self):
        a=self.db.reserve(self.ana,self.one)
        self.db.reserve(self.bruno,self.one)
        self.db.cancel_reservation(self.ana,a['id'])
        reservations=self.db.my_activity(self.bruno)['reservations']
        self.assertEqual(reservations[0]['status'],'ready')

    def test_reservation_auto_expires_after_48_hours(self):
        self.db.reserve(self.ana,self.one)
        self.db.reserve(self.bruno,self.one)
        self.clock[0]+=timedelta(hours=49)
        self.db.books()  # La reconciliación se ejecuta al consultar.
        self.assertEqual(self.db.my_activity(self.ana)['reservations'][0]['status'],'expired')
        self.assertEqual(self.db.my_activity(self.bruno)['reservations'][0]['status'],'ready')

    def test_cannot_bypass_ready_reservation(self):
        self.db.reserve(self.ana,self.one)
        self.assertCode(409,self.db.checkout,self.admin,self.one,self.bruno['id'])
        result=self.db.checkout(self.admin,self.one,self.ana['id'])
        self.assertIsInstance(result['id'],int)
        self.assertEqual(self.db.my_activity(self.ana)['reservations'][0]['status'],'fulfilled')

    def test_return_promotes_fifo_waiting(self):
        first=self.db.checkout(self.admin,self.one,self.ana['id'])
        self.db.reserve(self.bruno,self.one)
        self.assertEqual(self.db.my_activity(self.bruno)['reservations'][0]['status'],'waiting')
        self.db.return_loan(self.admin,first['id'])
        self.assertEqual(self.db.my_activity(self.bruno)['reservations'][0]['status'],'ready')

    def test_duplicate_active_loan_rejected(self):
        self.db.checkout(self.admin,self.multi,self.ana['id'])
        self.assertCode(409,self.db.checkout,self.admin,self.multi,self.ana['id'])

    def test_max_three_active_loans(self):
        ids=[b['id'] for b in self.db.books() if b['available']]
        for i in ids[:3]: self.db.checkout(self.admin,i,self.ana['id'])
        self.assertCode(409,self.db.checkout,self.admin,ids[3],self.ana['id'])

    def test_due_date_is_fourteen_calendar_days(self):
        loan=self.db.checkout(self.admin,self.one,self.ana['id'])
        self.assertEqual(loan['due_on'],'2026-12-03')

    def test_overdue_blocks_new_loan_and_reservation(self):
        self.db.checkout(self.admin,self.one,self.ana['id'])
        self.clock[0]+=timedelta(days=15)
        self.assertCode(409,self.db.checkout,self.admin,self.multi,self.ana['id'])
        self.assertCode(409,self.db.reserve,self.ana,self.multi)

    def test_one_renewal_adds_seven_days(self):
        loan=self.db.checkout(self.admin,self.one,self.ana['id'])
        result=self.db.renew(self.ana,loan['id'])
        self.assertEqual(result['due_on'],'2026-12-10')
        self.assertCode(409,self.db.renew,self.ana,loan['id'])

    def test_renewal_denied_if_someone_waiting(self):
        loan=self.db.checkout(self.admin,self.one,self.ana['id'])
        self.db.reserve(self.bruno,self.one)
        self.assertCode(409,self.db.renew,self.ana,loan['id'])

    def test_overdue_loan_cannot_be_renewed(self):
        loan=self.db.checkout(self.admin,self.one,self.ana['id'])
        self.clock[0]+=timedelta(days=15)
        self.assertCode(409,self.db.renew,self.ana,loan['id'])

    def test_stock_cannot_go_below_loans_and_ready_holds(self):
        self.db.checkout(self.admin,self.one,self.ana['id'])
        self.assertCode(400,self.db.save_book,self.admin,'Ficciones','Jorge Luis Borges','Literatura','9780802130303',0,self.one)
        # Con dos ejemplares comprometidos: 1 préstamo, 1 reserva lista.
        self.db.save_book(self.admin,'Ficciones','Jorge Luis Borges','Literatura','9780802130303',2,self.one)
        self.db.reserve(self.bruno,self.one)
        self.assertCode(409,self.db.save_book,self.admin,'Ficciones','Jorge Luis Borges','Literatura','9780802130303',1,self.one)

    def test_new_stock_promotes_queue(self):
        self.db.checkout(self.admin,self.one,self.ana['id'])
        self.db.reserve(self.bruno,self.one)
        self.db.save_book(self.admin,'Ficciones','Jorge Luis Borges','Literatura','9780802130303',2,self.one)
        self.assertEqual(self.db.my_activity(self.bruno)['reservations'][0]['status'],'ready')

    def test_roles_cannot_modify_books_or_loans(self):
        self.assertCode(403,self.db.save_book,self.ana,'Libro','Autor','Tema','',1)
        self.assertCode(403,self.db.checkout,self.ana,self.one,self.bruno['id'])
        self.assertCode(403,self.db.reserve,self.admin,self.one)

    def test_non_owner_cannot_cancel_reservation(self):
        r=self.db.reserve(self.ana,self.one)
        self.assertCode(404,self.db.cancel_reservation,self.bruno,r['id'])

    def test_catalog_case_insensitive_filter(self):
        self.assertEqual(self.db.books('borgES')[0]['title'],'Ficciones')

    def test_student_email_unique_and_password_validation(self):
        self.assertCode(409,self.db.add_student,self.admin,'Otra Ana','ana@bibliolab.test','Password123')
        self.assertCode(400,self.db.add_student,self.admin,'A','invalid','123')

    def test_concurrent_reservations_last_copy(self):
        barrier=threading.Barrier(3)
        results=[]
        lock=threading.Lock()
        def worker(u):
            barrier.wait()
            try: result=self.db.reserve(u,self.one)['status']
            except Exception as e: result=f'ERROR:{e}'
            with lock: results.append(result)
        t1=threading.Thread(target=worker,args=(self.ana,))
        t2=threading.Thread(target=worker,args=(self.bruno,))
        t1.start();t2.start();barrier.wait();t1.join();t2.join()
        self.assertCountEqual(results,['ready','waiting'])

    def test_multiple_concurrent_admin_checkouts_single_copy(self):
        barrier=threading.Barrier(3)
        results=[]
        lock=threading.Lock()
        def worker(uid):
            barrier.wait()
            try:self.db.checkout(self.admin,self.one,uid);result='OK'
            except DomainError as e:result=f'{e.status}'
            with lock:results.append(result)
        threads=[threading.Thread(target=worker,args=(u['id'],)) for u in (self.ana,self.bruno)]
        for t in threads:t.start()
        barrier.wait()
        for t in threads:t.join()
        self.assertCountEqual(results,['OK','409'])

if __name__=='__main__':unittest.main()
