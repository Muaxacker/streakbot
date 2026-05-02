"""
health.py — Minimal HTTP health check server for Koyeb

Koyeb requires an HTTP endpoint to confirm the service is alive.
This runs a tiny server on port 8000 alongside the bot.
"""

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass  # suppress access logs


def start_health_server(port: int = 8000):
    """Start the health check server in a background thread."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
