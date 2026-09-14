"""Action requests must not corrupt subsequent HTTP/1.1 polling."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import serve


class KeepAliveTests(unittest.TestCase):
    def setUp(self):
        self.project = tempfile.TemporaryDirectory(prefix="resume-http-")
        self.httpd, self.core = serve.create_server(self.project.name, port=0)
        self.worker = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.core.stop_background()
        self.httpd.server_close()
        self.worker.join(timeout=5)
        self.project.cleanup()

    def action_then_poll(self, path, body="{}"):
        connection = http.client.HTTPConnection("127.0.0.1", self.core.port, timeout=10)
        headers = {"X-Resume-Token": self.core.token, "Content-Type": "application/json"}
        try:
            connection.request("POST", path, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.assertEqual(response.status, 200, payload)
            connection.request("GET", "/api/events", headers=headers)
            response = connection.getresponse()
            payload = response.read()
            self.assertEqual(response.status, 200, payload)
            self.assertIn("events", json.loads(payload))
        finally:
            connection.close()

    def test_finish_then_poll(self):
        self.action_then_poll("/api/editing-done")

    def test_export_then_poll(self):
        # Isolate HTTP framing from the Typst runtime and resume content.
        with patch.object(self.core, "export_pdf", return_value={"ok": True}):
            self.action_then_poll("/api/export")

    def test_render_then_poll(self):
        with patch.object(self.core, "queue_render", return_value=False):
            self.action_then_poll("/api/render")

    def test_bodyless_local_action_then_poll(self):
        self.action_then_poll("/api/editing-done", body=None)

    def test_invalid_content_length_is_client_error_and_followup_request_works(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.core.port, timeout=10)
        headers = {
            "X-Resume-Token": self.core.token,
            "Content-Type": "application/json",
            "Content-Length": "not-a-number",
        }
        try:
            connection.request("PUT", "/api/resume", body="{}", headers=headers)
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn("Content-Length", response.read().decode("utf-8"))

            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", self.core.port, timeout=10)
            connection.request("GET", "/api/events", headers={
                "X-Resume-Token": self.core.token,
            })
            response = connection.getresponse()
            payload = response.read()
            self.assertEqual(response.status, 200, payload)
            self.assertIn("events", json.loads(payload))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
