"""Lógica de dominio y persistencia SQLite de BiblioLab.

Todas las operaciones que afectan ejemplares/colas corren dentro de BEGIN IMMEDIATE
para serializar escrituras concurrentes y evitar préstamos dobles.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Argentina/Buenos_Aires')

class DomainError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 260_000)
    return f'{salt.hex()}:{digest.hex()}'


def password_valid(password, stored):
    try:
        salt_hex, encoded = stored.split(':', 1)
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 260_000)
        return hmac.compare_digest(actual, bytes.fromhex(encoded))
    except (ValueError, AttributeError):
        return False


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
 password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','admin')),
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, author TEXT NOT NULL,
 category TEXT NOT NULL, isbn TEXT UNIQUE, copies INTEGER NOT NULL CHECK(copies >= 1),
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS loans (
 id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
 user_id INTEGER NOT NULL REFERENCES users(id), borrowed_at TEXT NOT NULL,
 due_on TEXT NOT NULL, returned_at TEXT, renewal_count INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_active_user_book
 ON loans(book_id,user_id) WHERE returned_at IS NULL;
CREATE TABLE IF NOT EXISTS reservations (
 id INTEGER PRIMARY KEY, book_id INTEGER NOT NULL REFERENCES books(id),
 user_id INTEGER NOT NULL REFERENCES users(id),
 status TEXT NOT NULL CHECK(status IN ('waiting','ready','fulfilled','cancelled','expired')),
 created_at TEXT NOT NULL, expires_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_active_reservation
 ON reservations(book_id,user_id) WHERE status IN ('waiting','ready');
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 created_at TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_res_book_status ON reservations(book_id,status,created_at,id);
CREATE INDEX IF NOT EXISTS idx_loans_book ON loans(book_id,returned_at);
'''


class Library:
    def __init__(self, path, now=None):
        self.path = path
        self.now = now or (lambda: datetime.now(TZ))
        self.initialize()

    def conn(self):
        con = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        con.execute('PRAGMA busy_timeout=15000')
        return con

    @contextmanager
    def transaction(self, write=False):
        con = self.conn()
        try:
            con.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with self.conn() as con:
            con.executescript(SCHEMA)
            con.execute('PRAGMA journal_mode=WAL')

    def stamp(self):
        return self.now().isoformat(timespec='seconds')

    def today(self):
        return self.now().date().isoformat()

    @staticmethod
    def row(row):
        return dict(row) if row is not None else None

    def ensure_seed(self, admin_password, demo=False):
        if not admin_password or len(admin_password) < 8:
            raise RuntimeError('ADMIN_PASSWORD debe tener al menos 8 caracteres')
        with self.transaction(True) as con:
            if not con.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
                con.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)',
                            ('Bibliotecario', 'admin@bibliolab.test', password_hash(admin_password), 'admin', self.stamp()))
            if demo:
                for name, email in [('Ana García', 'ana@bibliolab.test'), ('Bruno Pérez', 'bruno@bibliolab.test')]:
                    if not con.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
                        con.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)',
                                    (name, email, password_hash('Alumno2026!'), 'student', self.stamp()))
                if not con.execute('SELECT 1 FROM books').fetchone():
                    for title,author,cat,isbn,copies in [
                        ('El principito', 'Antoine de Saint-Exupéry', 'Literatura', '9780156012195', 2),
                        ('Ficciones', 'Jorge Luis Borges', 'Literatura', '9780802130303', 1),
                        ('Breve historia del tiempo', 'Stephen Hawking', 'Ciencia', '9780553380163', 1),
                        ('Introducción a Python', 'Varios autores', 'Tecnología', None, 3),
                        ('Cosmos', 'Carl Sagan', 'Ciencia', '9780345331359', 2),
                        ('El túnel', 'Ernesto Sabato', 'Literatura', '9788432216428', 2)
                    ]:
                        con.execute('INSERT INTO books(title,author,category,isbn,copies,created_at) VALUES (?,?,?,?,?,?)',
                                    (title,author,cat,isbn,copies,self.stamp()))

    def login(self, email, password):
        with self.transaction(True) as con:
            user = con.execute('SELECT * FROM users WHERE email=? AND active=1', (str(email).strip().lower(),)).fetchone()
            if not user or not password_valid(str(password), user['password_hash']):
                raise DomainError('Correo o contraseña incorrectos', 401)
            token = secrets.token_urlsafe(32)
            expires = (self.now() + timedelta(hours=12)).isoformat(timespec='seconds')
            con.execute('INSERT INTO sessions(token_hash,user_id,created_at,expires_at) VALUES (?,?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(), user['id'], self.stamp(), expires))
            return token, {k:user[k] for k in ('id','name','email','role')}

    def authenticate(self, token):
        if not token:
            raise DomainError('Iniciá sesión para continuar', 401)
        with self.transaction() as con:
            user = con.execute('''SELECT u.id,u.name,u.email,u.role FROM sessions s
               JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1''',
               (hashlib.sha256(token.encode()).hexdigest(), self.stamp())).fetchone()
            if not user:
                raise DomainError('Sesión vencida. Volvé a ingresar', 401)
            return self.row(user)

    def logout(self, token):
        with self.transaction(True) as con:
            con.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    @staticmethod
    def admin(user):
        if user['role'] != 'admin':
            raise DomainError('Solo el personal de biblioteca puede realizar esta operación', 403)

    @staticmethod
    def student(con, user_id):
        u = con.execute("SELECT * FROM users WHERE id=? AND role='student' AND active=1", (user_id,)).fetchone()
        if not u:
            raise DomainError('Alumno no encontrado', 404)
        return u

    @staticmethod
    def book(con, book_id):
        b = con.execute('SELECT * FROM books WHERE id=? AND active=1', (book_id,)).fetchone()
        if not b:
            raise DomainError('Libro no encontrado', 404)
        return b

    def has_overdue(self, con, user_id):
        return bool(con.execute('''SELECT 1 FROM loans WHERE user_id=? AND returned_at IS NULL
            AND due_on<? LIMIT 1''', (user_id, self.today())).fetchone())

    def eligible(self, con, user_id):
        self.student(con, user_id)
        if self.has_overdue(con, user_id):
            raise DomainError('Tenés préstamos vencidos. Primero devolvelos', 409)
        n = con.execute('SELECT COUNT(*) FROM loans WHERE user_id=? AND returned_at IS NULL', (user_id,)).fetchone()[0]
        if n >= 3:
            raise DomainError('Límite de 3 préstamos activos alcanzado', 409)

    def reconcile(self, con):
        # RN8: Expirar retiros vencidos y asignar ejemplares liberados por FIFO.
        con.execute("UPDATE reservations SET status='expired', expires_at=NULL WHERE status='ready' AND expires_at<=?",
                    (self.stamp(),))
        rows = con.execute('SELECT id,copies FROM books WHERE active=1').fetchall()
        for book in rows:
            borrowed = con.execute('SELECT COUNT(*) FROM loans WHERE book_id=? AND returned_at IS NULL', (book['id'],)).fetchone()[0]
            ready = con.execute("SELECT COUNT(*) FROM reservations WHERE book_id=? AND status='ready'", (book['id'],)).fetchone()[0]
            slots = max(0, book['copies'] - borrowed - ready)
            for waiting in con.execute('''SELECT id FROM reservations WHERE book_id=? AND status='waiting'
                 ORDER BY created_at,id LIMIT ?''', (book['id'],slots)).fetchall():
                con.execute("UPDATE reservations SET status='ready', expires_at=? WHERE id=?",
                            ((self.now()+timedelta(hours=48)).isoformat(timespec='seconds'), waiting['id']))

    def books(self, query=''):
        with self.transaction(True) as con:
            self.reconcile(con)
            term = f'%{str(query).strip()}%'
            data = con.execute('''SELECT b.id,b.title,b.author,b.category,b.isbn,b.copies,
              (SELECT COUNT(*) FROM loans l WHERE l.book_id=b.id AND l.returned_at IS NULL) AS borrowed,
              (SELECT COUNT(*) FROM reservations r WHERE r.book_id=b.id AND r.status='ready') AS held,
              (SELECT COUNT(*) FROM reservations r WHERE r.book_id=b.id AND r.status='waiting') AS waiting
              FROM books b WHERE b.active=1 AND (b.title LIKE ? OR b.author LIKE ? OR b.category LIKE ?)
              ORDER BY b.title''', (term,term,term)).fetchall()
            return [{**dict(b), 'available': max(0,b['copies']-b['borrowed']-b['held'])} for b in data]

    def reserve(self, user, book_id):
        if user['role'] != 'student':
            raise DomainError('Solo los alumnos pueden reservar', 403)
        with self.transaction(True) as con:
            self.reconcile(con)
            self.book(con, book_id)
            if self.has_overdue(con,user['id']):
                raise DomainError('No podés reservar mientras tengas préstamos vencidos',409)
            if con.execute('SELECT 1 FROM loans WHERE user_id=? AND book_id=? AND returned_at IS NULL', (user['id'],book_id)).fetchone():
                raise DomainError('Ya tenés prestado ese libro',409)
            if con.execute("SELECT 1 FROM reservations WHERE user_id=? AND book_id=? AND status IN ('waiting','ready')", (user['id'],book_id)).fetchone():
                raise DomainError('Ya tenés una reserva activa de ese libro',409)
            con.execute("INSERT INTO reservations(book_id,user_id,status,created_at) VALUES (?,?,'waiting',?)",
                        (book_id,user['id'],self.stamp()))
            rid = con.execute('SELECT last_insert_rowid()').fetchone()[0]
            self.reconcile(con)
            return self.row(con.execute('SELECT * FROM reservations WHERE id=?', (rid,)).fetchone())

    def cancel_reservation(self, user, reservation_id):
        with self.transaction(True) as con:
            self.reconcile(con)
            r = con.execute('SELECT * FROM reservations WHERE id=?', (reservation_id,)).fetchone()
            if not r or (r['user_id'] != user['id'] and user['role'] != 'admin'):
                raise DomainError('Reserva no encontrada',404)
            if r['status'] not in ('waiting','ready'):
                raise DomainError('Esta reserva ya no se puede cancelar',409)
            con.execute("UPDATE reservations SET status='cancelled',expires_at=NULL WHERE id=?", (reservation_id,))
            self.reconcile(con)
            return {'ok':True}

    def my_activity(self, user):
        with self.transaction(True) as con:
            self.reconcile(con)
            loans = con.execute('''SELECT l.id,l.book_id,b.title,l.borrowed_at,l.due_on,l.returned_at,l.renewal_count
                 FROM loans l JOIN books b ON b.id=l.book_id WHERE l.user_id=?
                 ORDER BY (l.returned_at IS NULL) DESC, l.id DESC''',(user['id'],)).fetchall()
            reservations = con.execute('''SELECT r.id,r.book_id,b.title,r.status,r.created_at,r.expires_at
                 FROM reservations r JOIN books b ON b.id=r.book_id WHERE r.user_id=? ORDER BY r.id DESC''',(user['id'],)).fetchall()
            return {'loans':[dict(r) for r in loans], 'reservations':[dict(r) for r in reservations], 'today':self.today()}

    def renew(self, user, loan_id):
        if user['role'] != 'student':
            raise DomainError('Solo alumnos renuevan sus préstamos',403)
        with self.transaction(True) as con:
            self.reconcile(con)
            loan = con.execute('SELECT * FROM loans WHERE id=? AND user_id=? AND returned_at IS NULL', (loan_id,user['id'])).fetchone()
            if not loan:
                raise DomainError('Préstamo no encontrado',404)
            if loan['due_on'] < self.today():
                raise DomainError('Un préstamo vencido no se puede renovar',409)
            if loan['renewal_count'] >= 1:
                raise DomainError('Solo se permite una renovación por préstamo',409)
            if con.execute("SELECT 1 FROM reservations WHERE book_id=? AND user_id<>? AND status IN ('waiting','ready')",(loan['book_id'],user['id'])).fetchone():
                raise DomainError('No se puede renovar: otro alumno está esperando el libro',409)
            new_due = (datetime.fromisoformat(loan['due_on']).date()+timedelta(days=7)).isoformat()
            con.execute('UPDATE loans SET due_on=?, renewal_count=1 WHERE id=?',(new_due,loan_id))
            return {'id':loan_id,'due_on':new_due,'renewal_count':1}

    def students(self, user):
        self.admin(user)
        with self.transaction() as con:
            return [dict(r) for r in con.execute("SELECT id,name,email,active FROM users WHERE role='student' ORDER BY name")]

    def add_student(self, user, name,email,password):
        self.admin(user)
        name,email=str(name).strip(),str(email).strip().lower()
        if len(name)<2 or len(name)>100 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) or len(str(password))<8:
            raise DomainError('Nombre, correo o contraseña inválidos (mínimo 8 caracteres)',400)
        with self.transaction(True) as con:
            try:
                con.execute('INSERT INTO users(name,email,password_hash,role,created_at) VALUES (?,?,?,?,?)',
                            (name,email,password_hash(password),'student',self.stamp()))
            except sqlite3.IntegrityError:
                raise DomainError('Ese correo ya está registrado',409)
            return {'id':con.execute('SELECT last_insert_rowid()').fetchone()[0], 'name':name,'email':email}

    def save_book(self,user,title,author,category,isbn,copies,book_id=None):
        self.admin(user)
        title,author,category = [str(x).strip() for x in (title,author,category)]
        isbn = str(isbn).strip() or None
        try: copies=int(copies)
        except (ValueError,TypeError): raise DomainError('Cantidad de ejemplares inválida',400)
        if not 2 <= len(title) <= 160 or not 2 <= len(author)<=120 or not 2<=len(category)<=60 or not 1<=copies<=1000:
            raise DomainError('Completá título, autor, categoría y entre 1 y 1000 ejemplares',400)
        if isbn and len(isbn)>30: raise DomainError('ISBN demasiado largo',400)
        with self.transaction(True) as con:
            self.reconcile(con)
            if book_id is not None:
                self.book(con,book_id)
                used=con.execute('SELECT COUNT(*) FROM loans WHERE book_id=? AND returned_at IS NULL',(book_id,)).fetchone()[0]
                held=con.execute("SELECT COUNT(*) FROM reservations WHERE book_id=? AND status='ready'",(book_id,)).fetchone()[0]
                if copies<used+held: raise DomainError('No podés reducir ejemplares por debajo de préstamos y reservas asignadas',409)
            try:
                if book_id is None:
                    con.execute('INSERT INTO books(title,author,category,isbn,copies,created_at) VALUES (?,?,?,?,?,?)',
                                (title,author,category,isbn,copies,self.stamp()))
                    book_id=con.execute('SELECT last_insert_rowid()').fetchone()[0]
                else:
                    con.execute('UPDATE books SET title=?,author=?,category=?,isbn=?,copies=? WHERE id=?',
                                (title,author,category,isbn,copies,book_id))
            except sqlite3.IntegrityError:
                raise DomainError('Ese ISBN ya existe',409)
            self.reconcile(con)
            return {'id':book_id,'title':title,'author':author,'category':category,'isbn':isbn,'copies':copies}

    def checkout(self, user, book_id, student_id):
        self.admin(user)
        with self.transaction(True) as con:
            self.reconcile(con)
            book=self.book(con,book_id)
            self.eligible(con,student_id)
            if con.execute('SELECT 1 FROM loans WHERE book_id=? AND user_id=? AND returned_at IS NULL',(book_id,student_id)).fetchone():
                raise DomainError('Ese alumno ya tiene un ejemplar del libro',409)
            occupied=con.execute('SELECT COUNT(*) FROM loans WHERE book_id=? AND returned_at IS NULL',(book_id,)).fetchone()[0]
            ready=con.execute("SELECT * FROM reservations WHERE book_id=? AND user_id=? AND status='ready'",(book_id,student_id)).fetchone()
            held=con.execute("SELECT COUNT(*) FROM reservations WHERE book_id=? AND status='ready'",(book_id,)).fetchone()[0]
            if occupied>=book['copies'] or (not ready and occupied+held>=book['copies']):
                raise DomainError('No hay ejemplares libres para ese alumno; respetar reservas',409)
            due=(self.now().date()+timedelta(days=14)).isoformat()
            con.execute('INSERT INTO loans(book_id,user_id,borrowed_at,due_on) VALUES (?,?,?,?)',
                        (book_id,student_id,self.stamp(),due))
            loan_id=con.execute('SELECT last_insert_rowid()').fetchone()[0]
            if ready:
                con.execute("UPDATE reservations SET status='fulfilled',expires_at=NULL WHERE id=?",(ready['id'],))
            # Si se puede retirar un ejemplar libre, su reserva en espera no debería existir,
            # pero se resuelve por seguridad ante modificaciones de inventario.
            con.execute("UPDATE reservations SET status='fulfilled',expires_at=NULL WHERE book_id=? AND user_id=? AND status='waiting'",(book_id,student_id))
            self.reconcile(con)
            return {'id':loan_id,'book_id':book_id,'user_id':student_id,'due_on':due}

    def return_loan(self,user,loan_id):
        self.admin(user)
        with self.transaction(True) as con:
            self.reconcile(con)
            loan=con.execute('SELECT id FROM loans WHERE id=? AND returned_at IS NULL',(loan_id,)).fetchone()
            if not loan: raise DomainError('Préstamo activo no encontrado',404)
            con.execute('UPDATE loans SET returned_at=? WHERE id=?',(self.stamp(),loan_id))
            self.reconcile(con)
            return {'ok':True,'returned_at':self.stamp()}

    def admin_loans(self,user):
        self.admin(user)
        with self.transaction(True) as con:
            self.reconcile(con)
            data=con.execute('''SELECT l.id,l.book_id,b.title,l.user_id,u.name AS student,
               u.email,l.due_on,l.borrowed_at,l.returned_at,l.renewal_count
               FROM loans l JOIN books b ON l.book_id=b.id JOIN users u ON u.id=l.user_id
               ORDER BY (l.returned_at IS NULL) DESC,l.due_on,l.id DESC''').fetchall()
            return {'loans':[dict(x) for x in data], 'today':self.today()}

    def admin_reservations(self,user):
        self.admin(user)
        with self.transaction(True) as con:
            self.reconcile(con)
            return [dict(x) for x in con.execute('''SELECT r.id,r.status,r.created_at,r.expires_at,
              b.title,u.name AS student,u.email FROM reservations r JOIN books b ON b.id=r.book_id
              JOIN users u ON u.id=r.user_id WHERE r.status IN ('ready','waiting')
              ORDER BY CASE r.status WHEN 'ready' THEN 0 ELSE 1 END,r.created_at,r.id''')]

    def dashboard(self,user):
        self.admin(user)
        with self.transaction(True) as con:
            self.reconcile(con)
            def count(query):return con.execute(query).fetchone()[0]
            return {'titles':count('SELECT COUNT(*) FROM books WHERE active=1'),
                    'students':count("SELECT COUNT(*) FROM users WHERE role='student' AND active=1"),
                    'active_loans':count('SELECT COUNT(*) FROM loans WHERE returned_at IS NULL'),
                    'overdue':con.execute('SELECT COUNT(*) FROM loans WHERE returned_at IS NULL AND due_on<?',(self.today(),)).fetchone()[0],
                    'waiting':count("SELECT COUNT(*) FROM reservations WHERE status='waiting'"),
                    'ready':count("SELECT COUNT(*) FROM reservations WHERE status='ready'")}
