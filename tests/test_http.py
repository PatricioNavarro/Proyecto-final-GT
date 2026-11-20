"""Smoke tests HTTP reales con ThreadingHTTPServer y Cookie de sesión."""
import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from core import Library
from server import make_handler

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.db=Library(str(Path(cls.temp.name)/'app.sqlite3'))
        cls.db.ensure_seed('ClaveAdminSegura!',demo=True)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(cls.db))
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=2);cls.temp.cleanup()

    def request(self,method,path,body=None,cookie=None,origin=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        headers={}
        if body is not None:
            headers['Content-Type']='application/json';body=json.dumps(body)
        if cookie:headers['Cookie']=cookie
        if origin:headers['Origin']=origin
        conn.request(method,path,body=body,headers=headers)
        response=conn.getresponse();raw=response.read()
        result=(response.status,dict(response.getheaders()),json.loads(raw) if '/api/' in path else raw)
        conn.close();return result

    def test_health_and_static(self):
        code,_,body=self.request('GET','/api/health')
        self.assertEqual(code,200)
        self.assertTrue(body['ok'])
        code,_,html=self.request('GET','/')
        self.assertEqual(code,200)
        self.assertIn(b'BiblioLab',html)

    def test_auth_and_authorization(self):
        code,_,body=self.request('GET','/api/admin/dashboard')
        self.assertEqual(code,401)
        code,h,body=self.request('POST','/api/auth/login',{'email':'ana@bibliolab.test','password':'Alumno2026!'})
        self.assertEqual(code,200)
        cookie=h['Set-Cookie'].split(';')[0]
        code,_,body=self.request('GET','/api/books',cookie=cookie)
        self.assertEqual(code,200)
        self.assertEqual(len(body['books']),6)
        code,_,body=self.request('GET','/api/admin/dashboard',cookie=cookie)
        self.assertEqual(code,403)
        code,_,body=self.request('POST','/api/auth/logout',cookie=cookie)
        self.assertEqual(code,200)
        code,_,body=self.request('GET','/api/me',cookie=cookie)
        self.assertEqual(code,401)

    def test_cross_origin_write_rejected(self):
        code,_,body=self.request('POST','/api/auth/login',{'email':'a','password':'b'},origin='https://evil.example')
        self.assertEqual(code,403)

    def test_reject_non_json_and_bad_path(self):
        code,_,body=self.request('GET','/api/nonexistent')
        self.assertEqual(code,401) # se autentica antes de resolver rutas privadas
        code,_,body=self.request('GET','/../../etc/passwd')
        self.assertEqual(code,404)

if __name__=='__main__':unittest.main()
