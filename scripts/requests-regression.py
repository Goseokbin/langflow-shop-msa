"""Offline HTTP behavior used by this application: GET/POST, JSON, and error handling."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(503 if self.path == '/error' else 200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


server = HTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}'
try:
    with requests.Session() as session:
        session.trust_env = False
        assert session.get(url, timeout=2).json() == {'ok': True}
        assert session.post(url, json={'message': 'demo'}, timeout=2).json() == {'message': 'demo'}
        try:
            session.get(url + '/error', timeout=2).raise_for_status()
        except requests.HTTPError:
            pass
        else:
            raise AssertionError('Non-success HTTP response must raise')
    print(json.dumps({'http_get': 'passed', 'json_post': 'passed', 'http_error': 'passed'}))
finally:
    server.shutdown()
