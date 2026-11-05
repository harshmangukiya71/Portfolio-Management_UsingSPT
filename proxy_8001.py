import http.server
import socketserver
import urllib.request
import urllib.error

PORT = 8001
TARGET = "http://localhost:8000"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_request(self):
        url = TARGET + self.path
        headers = {k: v for k, v in self.headers.items() if k.lower() != 'host'}
        data = None
        if 'content-length' in self.headers:
            length = int(self.headers['content-length'])
            data = self.rfile.read(length)
        
        req = urllib.request.Request(url, data=data, headers=headers, method=self.command)
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ['transfer-encoding', 'content-length']:
                        self.send_header(k, v)
                content = resp.read()
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                if k.lower() not in ['transfer-encoding', 'content-length']:
                    self.send_header(k, v)
            content = e.read()
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as exc:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(exc).encode())

    def do_GET(self): self.do_request()
    def do_POST(self): self.do_request()
    def do_PUT(self): self.do_request()
    def do_DELETE(self): self.do_request()
    def do_PATCH(self): self.do_request()
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', '*')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
        print(f"Proxying port {PORT} -> {TARGET}")
        httpd.serve_forever()
