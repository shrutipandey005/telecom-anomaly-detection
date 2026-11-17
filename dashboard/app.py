"""
Local Web Dashboard Server for Telecom Anomaly Detection
Provides interactive operations interface for Thiruvananthapuram network reviewers.
"""

import os
import sys
import json
import sqlite3
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.config import DB_PATH, DATA_DIR

PORT = 8088
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")


class DashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/dashboard":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(HTML_FILE, "rb") as f:
                self.wfile.write(f.read())
        elif parsed.path == "/api/alerts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            alerts = []
            if os.path.exists(DB_PATH):
                with sqlite3.connect(DB_PATH) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM daily_review_queue LIMIT 100")
                    rows = cursor.fetchall()
                    alerts = [dict(r) for r in rows]
            self.wfile.write(json.dumps(alerts).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/feedback":
            content_length = int(self.headers["Content-Length"])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode("utf-8"))

            from src.feedback_loop import AdaptiveFeedbackTuner
            tuner = AdaptiveFeedbackTuner(DB_PATH)
            tuner.record_reviewer_feedback(
                alert_id=payload.get("alert_id", "UNKNOWN"),
                subscriber_id=payload.get("subscriber_id", "UNKNOWN"),
                reason_code=payload.get("reason_code", "UNKNOWN"),
                anomaly_score=float(payload.get("anomaly_score", 0.0)),
                decision=payload.get("decision", "CONFIRMED_TRUE"),
                notes=payload.get("notes", ""),
            )
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "SUCCESS"}).encode("utf-8"))
        else:
            self.send_error(404, "Endpoint not found")


def main():
    print(f"[*] Starting Ananthapuri FibreNet Review Dashboard on http://localhost:{PORT}")
    print(f"[*] Static dashboard page: {HTML_FILE}")
    print("    Press Ctrl+C to stop the server.")
    with socketserver.TCPServer(("", PORT), DashboardRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] Stopping dashboard server.")


if __name__ == "__main__":
    main()
