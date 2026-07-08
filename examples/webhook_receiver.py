from http.server import BaseHTTPRequestHandler, HTTPServer

class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length)
        print("Received mock OpsLens webhook:", body.decode())
        self.send_response(204)
        self.end_headers()

HTTPServer(("127.0.0.1", 8099), Receiver).serve_forever()
