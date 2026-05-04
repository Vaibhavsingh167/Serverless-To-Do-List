"""
Local Development Server for the Serverless To-Do List

Simulates API Gateway + Lambda locally using Python's built-in HTTP server.
Uses an in-memory store instead of DynamoDB so no AWS credentials are needed.
Serves the frontend on the same origin to avoid CORS issues during dev.

Usage:
    python local_server.py
    Open http://localhost:3000 in your browser
"""

import json
import uuid
import time
import os
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

# ============================================================
# In-memory todo store (replaces DynamoDB for local development)
# ============================================================
todos_db = {}

# Seed with sample data so the UI isn't empty on first load
SEED_TODOS = [
    {"title": "Deploy this app to AWS", "completed": False},
    {"title": "Configure S3 static hosting", "completed": False},
    {"title": "Set up API Gateway endpoints", "completed": True},
    {"title": "Write Lambda CRUD functions", "completed": True},
    {"title": "Create DynamoDB table", "completed": True},
]

for seed in SEED_TODOS:
    todo_id = str(uuid.uuid4())
    todos_db[todo_id] = {
        "id": todo_id,
        "title": seed["title"],
        "completed": seed["completed"],
        "createdAt": int(time.time() * 1000) - len(todos_db) * 60000,
    }


# ============================================================
# Request Handler — serves frontend + API routes
# ============================================================
class LocalDevHandler(SimpleHTTPRequestHandler):
    """Handles both static file serving (frontend) and API routes."""

    # Serve frontend files from the frontend/ directory
    def translate_path(self, path):
        """Override to serve files from frontend/ directory."""
        parsed = urlparse(path)
        clean_path = parsed.path

        # API routes are handled separately
        if clean_path.startswith("/todos"):
            return None

        # Serve frontend files
        if clean_path == "/":
            clean_path = "/index.html"

        frontend_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "frontend"
        )
        return os.path.join(frontend_dir, clean_path.lstrip("/"))

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self._send_cors_response(200)

    def do_GET(self):
        """Handle GET requests — either API or static files."""
        parsed = urlparse(self.path)

        if parsed.path == "/todos":
            # GET /todos — return all todos
            all_todos = list(todos_db.values())
            self._send_json(200, {"todos": all_todos})
        elif parsed.path.startswith("/todos"):
            self._send_json(404, {"error": "Not found"})
        else:
            # Serve static frontend files
            super().do_GET()

    def do_POST(self):
        """Handle POST /todos — create a new todo."""
        if self.path != "/todos":
            self._send_json(404, {"error": "Not found"})
            return

        body = self._read_body()
        title = body.get("title", "").strip()

        if not title:
            self._send_json(400, {"error": "Title is required"})
            return

        todo = {
            "id": str(uuid.uuid4()),
            "title": title,
            "completed": False,
            "createdAt": int(time.time() * 1000),
        }
        todos_db[todo["id"]] = todo
        self._send_json(201, {"todo": todo})

    def do_PUT(self):
        """Handle PUT /todos/{id} — update a todo."""
        match = re.match(r"^/todos/([a-f0-9-]+)$", self.path)
        if not match:
            self._send_json(404, {"error": "Not found"})
            return

        todo_id = match.group(1)
        if todo_id not in todos_db:
            self._send_json(404, {"error": "Todo not found"})
            return

        body = self._read_body()
        todo = todos_db[todo_id]

        if "completed" in body:
            todo["completed"] = body["completed"]
        if "title" in body:
            todo["title"] = body["title"]

        self._send_json(200, {"todo": todo})

    def do_DELETE(self):
        """Handle DELETE /todos/{id} — delete a todo."""
        match = re.match(r"^/todos/([a-f0-9-]+)$", self.path)
        if not match:
            self._send_json(404, {"error": "Not found"})
            return

        todo_id = match.group(1)
        if todo_id in todos_db:
            del todos_db[todo_id]

        self._send_json(200, {"message": "Todo deleted"})

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _read_body(self):
        """Read and parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return {}

    def _send_json(self, status, data):
        """Send a JSON response with CORS headers."""
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_response(self, status):
        """Send an empty response with CORS headers (for OPTIONS)."""
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt, *args):
        """Simple log format for Windows compatibility."""
        print(f"  {fmt % args}")


# ============================================================
# Main — Start the server
# ============================================================
if __name__ == "__main__":
    PORT = 3000
    server = HTTPServer(("0.0.0.0", PORT), LocalDevHandler)

    print()
    print("  +--------------------------------------------+")
    print("  |                                            |")
    print("  |   Serverless To-Do List -- Local Dev       |")
    print("  |                                            |")
    print(f"  |   http://localhost:{PORT}                    |")
    print("  |                                            |")
    print("  |   API routes:                              |")
    print("  |     GET    /todos                          |")
    print("  |     POST   /todos                          |")
    print("  |     PUT    /todos/{{id}}                     |")
    print("  |     DELETE /todos/{{id}}                     |")
    print("  |                                            |")
    print("  |   Press Ctrl+C to stop                     |")
    print("  |                                            |")
    print("  +--------------------------------------------+")
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()
