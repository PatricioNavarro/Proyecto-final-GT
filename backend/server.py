"""Servidor HTTP sin dependencias externas: API REST y frontend en un origen."""
import json
import os
import re
import sys
import traceback
from datetime import datetime
from email.utils import formatdate
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import Library, DomainError

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / 'frontend'
MIMES = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8',
         '.js':'text/javascript; charset=utf-8','.svg':'image/svg+xml','.ico':'image/x-icon'}


def make_handler(library, production=False):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'BiblioLab/1.0'
        def log_message(self, fmt, *args):
            print('%s - %s' % (self.address_string(), fmt % args), flush=True)

        def headers_common(self):
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','same-origin')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Cache-Control','no-store')

        def reply(self, data, status=200, cookie=None):
            raw=json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.headers_common()
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(raw)))
            if cookie is not None:
                attrs = f'Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if cookie == "" else 43200}'
                if production: attrs += '; Secure'
                self.send_header('Set-Cookie',f'session={cookie}; {attrs}')
            self.end_headers()
            self.wfile.write(raw)

        def current_token(self):
            c=SimpleCookie()
            try: c.load(self.headers.get('Cookie',''))
            except Exception: return ''
            return c['session'].value if 'session' in c else ''

        def user(self):
            return library.authenticate(self.current_token())

        def payload(self):
            if self.headers.get('Content-Type','').split(';')[0].strip().lower()!='application/json':
                raise DomainError('Enviar JSON (Content-Type: application/json)',415)
            try: length=int(self.headers.get('Content-Length','0'))
            except ValueError: raise DomainError('Longitud de solicitud inválida')
            if length < 0 or length>32768: raise DomainError('Solicitud demasiado grande',413)
            try: data=json.loads(self.rfile.read(length))
            except (json.JSONDecodeError,UnicodeDecodeError): raise DomainError('JSON inválido')
            if not isinstance(data,dict): raise DomainError('Se esperaba un objeto JSON')
            return data

        def csrf_guard(self):
            # Sin CORS ni formularios cross-site: sólo JSON y origen propio.
            origin=self.headers.get('Origin')
            if origin:
                requested=urlsplit(origin).netloc.lower()
                host=self.headers.get('X-Forwarded-Host',self.headers.get('Host','')).lower()
                if requested != host:
                    raise DomainError('Origen no permitido',403)

        def do_GET(self): self.dispatch('GET')
        def do_POST(self): self.dispatch('POST')
        def do_PATCH(self): self.dispatch('PATCH')
        def do_DELETE(self): self.dispatch('DELETE')
        def do_OPTIONS(self): self.reply({'error':'CORS no habilitado'},405)

        def dispatch(self,method):
            route=urlsplit(self.path).path
            try:
                if method in ('POST','PATCH','DELETE'): self.csrf_guard()
                if route.startswith('/api/'):
                    self.api(method,route)
                elif method=='GET': self.static(route)
                else: raise DomainError('Ruta no encontrada',404)
            except DomainError as ex:
                self.reply({'error':str(ex)},ex.status)
            except (TypeError,ValueError,KeyError) as ex:
                self.reply({'error':'Datos de entrada inválidos'},400)
            except Exception as ex:
                traceback.print_exc()
                self.reply({'error':'Error interno del servidor'},500)

        def api(self,method,route):
            if (method,route)==('GET','/api/health'):
                return self.reply({'ok':True,'app':'BiblioLab'})
            if (method,route)==('POST','/api/auth/login'):
                data=self.payload()
                token,user=library.login(data.get('email',''),data.get('password',''))
                return self.reply({'user':user},cookie=token)
            if (method,route)==('POST','/api/auth/logout'):
                token=self.current_token()
                if token: library.logout(token)
                return self.reply({'ok':True},cookie='')
            user=self.user()
            if (method,route)==('GET','/api/me'): return self.reply({'user':user})
            if (method,route)==('GET','/api/books'):
                q=parse_qs(urlsplit(self.path).query).get('q',[''])[0][:80]
                return self.reply({'books':library.books(q)})
            if (method,route)==('GET','/api/my'): return self.reply(library.my_activity(user))
            if (method,route)==('POST','/api/reservations'):
                p=self.payload()
                return self.reply({'reservation':library.reserve(user,int(p['book_id']))},201)
            match=re.fullmatch(r'/api/reservations/(\d+)',route)
            if method=='DELETE' and match:
                return self.reply(library.cancel_reservation(user,int(match.group(1))))
            match=re.fullmatch(r'/api/loans/(\d+)/renew',route)
            if method=='POST' and match:
                return self.reply({'loan':library.renew(user,int(match.group(1)))})
            if (method,route)==('GET','/api/admin/dashboard'):
                return self.reply(library.dashboard(user))
            if (method,route)==('GET','/api/admin/students'):
                return self.reply({'students':library.students(user)})
            if (method,route)==('POST','/api/admin/students'):
                p=self.payload()
                return self.reply({'student':library.add_student(user,p['name'],p['email'],p['password'])},201)
            if (method,route)==('POST','/api/admin/books'):
                p=self.payload()
                return self.reply({'book':library.save_book(user,p['title'],p['author'],p['category'],p.get('isbn',''),p['copies'])},201)
            match=re.fullmatch(r'/api/admin/books/(\d+)',route)
            if method=='PATCH' and match:
                p=self.payload()
                return self.reply({'book':library.save_book(user,p['title'],p['author'],p['category'],p.get('isbn',''),p['copies'],int(match.group(1)))})
            if (method,route)==('POST','/api/admin/checkout'):
                p=self.payload()
                return self.reply({'loan':library.checkout(user,int(p['book_id']),int(p['user_id']))},201)
            match=re.fullmatch(r'/api/admin/loans/(\d+)/return',route)
            if method=='POST' and match:
                return self.reply(library.return_loan(user,int(match.group(1))))
            if (method,route)==('GET','/api/admin/loans'):
                return self.reply(library.admin_loans(user))
            if (method,route)==('GET','/api/admin/reservations'):
                return self.reply({'reservations':library.admin_reservations(user)})
            raise DomainError('Ruta no encontrada',404)

        def static(self,route):
            if route in ('','/'): route='/index.html'
            safe=(STATIC/route.lstrip('/')).resolve()
            if not safe.is_relative_to(STATIC) or not safe.is_file():
                raise DomainError('Archivo no encontrado',404)
            content=safe.read_bytes()
            self.send_response(200)
            self.headers_common()
            self.send_header('Content-Type',MIMES.get(safe.suffix,'application/octet-stream'))
            self.send_header('Content-Length',str(len(content)))
            self.end_headers()
            self.wfile.write(content)
    return Handler


def run():
    env=os.getenv('APP_ENV','demo').lower()
    production=(env=='production')
    password=os.getenv('ADMIN_PASSWORD')
    if not password and not production:
        password='Demo2026!'
        print('AVISO: contraseña demo activa. No desplegar públicamente así.',flush=True)
    if not password or len(password)<8:
        raise RuntimeError('Configurá ADMIN_PASSWORD (mínimo 8 caracteres) antes de ejecutar en producción')
    db_path=os.getenv('DB_PATH',str(ROOT/'data'/'bibliolab.sqlite3'))
    library=Library(db_path)
    library.ensure_seed(password,demo=os.getenv('DEMO_SEED','1' if not production else '0')=='1')
    port=int(os.getenv('PORT','8000'))
    server=ThreadingHTTPServer(('0.0.0.0',port),make_handler(library,production=production))
    print(f'BiblioLab disponible en http://localhost:{port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__=='__main__': run()
