"""Vercel serverless function for free-form Wanderly policy questions.

Lets the chat widget ask about cancellation, baggage, or insurance policies
after an itinerary is generated. Claude answers using the
search_travel_policies tool (agent_core.py, rag.py) instead of guessing.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic

from agent_core import run_agent


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length else b"{}"

        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body."})
            return

        question = (payload.get("question") or "").strip()
        if not question:
            self._send_json(400, {"error": "Missing 'question'."})
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._send_json(
                500, {"error": "Server is missing ANTHROPIC_API_KEY. Set it in the Vercel project's environment variables."}
            )
            return

        client = anthropic.Anthropic(api_key=api_key)
        messages = [{"role": "user", "content": question}]

        try:
            reply = run_agent(client, messages)
        except Exception as exc:  # noqa: BLE001 - surface any Claude API failure to the widget
            self._send_json(502, {"error": f"Claude request failed: {exc}"})
            return

        self._send_json(200, {"reply": reply})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
