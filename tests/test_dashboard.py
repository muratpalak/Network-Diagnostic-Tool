"""Offline tests for the real desktop dashboard HTTP API and validation."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch
from netdiag.dashboard import AppState, make_server, validate_host, validate_url, trace_route

class ValidationTests(unittest.TestCase):
    def test_hosts(self):
        for host in ('example.com', '1.1.1.1', 'localhost', '::1'):
            self.assertEqual(validate_host(host),host)
    def test_reject_host_injection(self):
        for host in ('a;rm -rf /', '-exec', 'example.com/path', 'x\ny', 'bad..domain'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                validate_host(host)
    def test_https_validation(self):
        self.assertEqual(validate_url('https://example.com/abc'), 'https://example.com/abc')
        for url in ('http://example.com', 'https://user:pass@example.com', 'https://example.com/#frag', 'javascript:alert(1)', 'https://example.com:999999'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
    @patch('netdiag.dashboard.run_command', return_value={'ok':False,'stdout':'','stderr':'not found','elapsed_ms':2})
    def test_traceroute_unavailable(self, mock_run):
        self.assertEqual(trace_route('example.com', 'Linux')['status'],'WARN')

class AppStateTests(unittest.TestCase):
    @patch('netdiag.dashboard.inspect_local_network')
    @patch('netdiag.dashboard.check_dns')
    def test_real_result_is_recorded(self, dns, local):
        local.return_value={'os':'test','hostname':'test','interfaces':[],'default_gateway':None,'dns_servers':[],'collection_errors':[]}
        dns.return_value={'name':'DNS resolution','status':'PASS','message':'Resolved','duration_ms':1,'details':{'domain':'example.com'}}
        state=AppState()
        result=state.do({'kind':'dns','target':'example.com'})
        self.assertEqual(result['tests']['dns']['status'],'PASS')
        self.assertEqual(len(result['history']),1)
    def test_demo_rejects_tests(self):
        state=AppState(demo=True)
        with self.assertRaises(ValueError):
            state.do({'kind':'dns'})

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(demo=True)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
    def request(self, method, path, body=None, headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1],timeout=5)
        conn.request(method,path,body=body,headers=headers or {})
        resp=conn.getresponse()
        data=resp.read()
        status=resp.status
        conn.close()
        return status,data
    def test_dashboard_serves_page_and_assets(self):
        for path in ('/','/assets/style.css','/assets/app.js'):
            status,body=self.request('GET',path)
            self.assertEqual(status,200)
            self.assertTrue(body)
    def test_state_and_reports(self):
        status,body=self.request('GET','/api/state')
        self.assertEqual(status,200)
        self.assertTrue(json.loads(body)['demo'])
        for path in ('/api/report.html','/api/report.json'):
            status,body=self.request('GET',path)
            self.assertEqual(status,200)
            self.assertTrue(body)
        self.assertIn(b'DEMO DATA',self.request('GET','/api/report.html')[1])
    def test_reject_post_wrong_content_type(self):
        status,_=self.request('POST','/api/test','kind=dns',{'Content-Type':'application/x-www-form-urlencoded'})
        self.assertEqual(status,415)
    def test_demo_rejects_live_probes(self):
        status,body=self.request('POST','/api/test',json.dumps({'kind':'dns'}),{'Content-Type':'application/json'})
        self.assertEqual(status,400)
        self.assertIn(b'read-only',body)
    def test_block_bad_origin(self):
        status,_=self.request('POST','/api/test',json.dumps({'kind':'dns'}),{'Content-Type':'application/json','Origin':'https://evil.example'})
        self.assertEqual(status,403)
    def test_reject_path_traversal(self):
        status,_=self.request('GET','/assets/../../etc/passwd')
        self.assertEqual(status,404)

if __name__ == '__main__':
    unittest.main()
