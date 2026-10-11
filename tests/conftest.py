import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytest  # noqa: E402

LEAD = {"lead_id": "T1", "contact_name": "Ananya Mehta", "title": "CHRO", "company": "Brightline Logistics",
        "industry": "Logistics", "employees": "650", "city": "Gurugram", "current_hr_tool": "Excel + manual payroll",
        "recent_signal": "Opened 2 new warehouses and hiring 200 staff", "lead_source": "Webinar",
        "budget_status": "Approved", "timeline": "0-3 months"}


@pytest.fixture
def lead():
    return dict(LEAD)


@pytest.fixture
def nolog():
    return lambda *a: None


class MockLLM:
    """A fake OpenAI-compatible chat endpoint. `responder(request_json)` returns (status, body_dict_or_text, headers)."""

    def __init__(self, responder):
        self.responder = responder
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"body": body, "auth": self.headers.get("Authorization")})
                status, payload, headers = outer.responder(body)
                data = payload if isinstance(payload, str) else json.dumps(payload)
                self.send_response(status)
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data.encode())

            def log_message(self, *a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1/chat/completions"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


def completion(text):
    return {"choices": [{"message": {"content": text}}]}


@pytest.fixture
def mock_llm():
    servers = []

    def make(responder):
        s = MockLLM(responder)
        servers.append(s)
        return s
    yield make
    for s in servers:
        s.close()
