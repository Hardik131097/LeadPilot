"""The Streamlit app itself, driven headlessly."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from streamlit.testing.v1 import AppTest

from conftest import ROOT

APP = os.path.join(ROOT, "app.py")


def test_app_loads_in_demo_mode():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert any("Demo mode" in i.value for i in at.info)


def test_run_button_produces_results_and_tabs():
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.button[0].click().run()
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert "Leads processed" in labels


def test_approved_email_is_posted_to_n8n_webhook():
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *a):
            pass
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.button[0].click().run()
    at.button_group[0].set_value("✉️ Outreach approval").run()
    at.checkbox[0].check().run()
    [t for t in at.text_input if t.label == "n8n webhook URL"][0].input(
        f"http://127.0.0.1:{srv.server_port}/webhook/leadpilot").run()
    [t for t in at.text_input if t.label.startswith("Demo recipient")][0].input("me@example.com").run()
    [b for b in at.button if "n8n" in b.label][0].click().run()
    srv.shutdown()
    assert got and got[0]["emails"][0]["to"] == "me@example.com"
    assert got[0]["emails"][0]["email_body"].startswith("[DEMO")


def test_approving_a_draft_keeps_the_rep_on_the_approval_view():
    """Regression: with st.tabs, every approval threw the rep back to the first tab."""
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.button[0].click().run()
    at.button_group[0].set_value("✉️ Outreach approval").run()
    at.checkbox[0].check().run()
    assert at.button_group[0].value == "✉️ Outreach approval"
    assert any("1 of" in m.value and "approved" in m.value for m in at.markdown)
