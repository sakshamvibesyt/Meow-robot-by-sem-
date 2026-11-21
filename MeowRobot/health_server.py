import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

PORT = int(os.environ.get("PORT", "10000"))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health", "/health/"):
            self.send_error(404)
            return
        body = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MeowRobot Status</title>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#101018;color:#fff;font-family:Arial,sans-serif}
.card{padding:32px 26px;text-align:center;background:#1d1d2b;border:1px solid #39304c;border-radius:18px;max-width:420px}
h1{color:#bd7aff;margin-top:0}.online{color:#39df91;font-weight:bold}p{color:#c9c4d3}
</style></head><body><main class="card"><h1>🐱 MeowRobot</h1>
<div class="online">● ONLINE</div><p>HTTP health server is running.</p></main></body></html>""".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    Thread(target=server.serve_forever, daemon=True, name="health-http").start()
    print(f"MeowRobot health server listening on 0.0.0.0:{PORT}", flush=True)
    return server
