
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

PORT = int(os.environ.get("PORT", 10000))


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/health/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            page = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>MeowRobot Status</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{
                        background: #101018;
                        color: white;
                        font-family: Arial;
                        text-align: center;
                        padding: 60px 15px;
                    }}
                    .card {{
                        max-width: 420px;
                        margin: auto;
                        padding: 30px;
                        background: #1d1d2b;
                        border-radius: 18px;
                    }}
                    h1 {{ color: #bd7aff; }}
                    .online {{ color: #39df91; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>🐱 MeowRobot</h1>
                    <h2 class="online">● ONLINE</h2>
                    <p>Bot Status: Running</p>
                    <p>HTTP Server: Active</p>
                    <p>Port: {PORT}</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(page.encode("utf-8"))
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), HealthHandler)
    Thread(target=server.serve_forever, daemon=True).start()
    print(f"MeowRobot HTTP server started on port {PORT}")
  
