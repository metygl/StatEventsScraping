"""
Vercel Python serverless function for handling feedback form submissions.
Creates GitHub Issues from feedback data.
"""

import json
import os
import http.client
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse


GITHUB_REPO = "metygl/StatEventsScraping"
FEEDBACK_TYPES = {
    "new_source": "New Source Suggestion",
    "bug_report": "Bug Report",
    "feature_request": "Feature Request",
    "other": "Other",
}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            self._respond(400, {"success": False, "error": "Invalid JSON"})
            return

        # Honeypot check
        if data.get("website"):
            self._respond(200, {"success": True})
            return

        message = (data.get("message") or "").strip()
        if not message:
            self._respond(400, {"success": False, "error": "Message is required"})
            return
        if len(message) > 2000:
            self._respond(400, {"success": False, "error": "Message too long (max 2000 chars)"})
            return

        feedback_type = data.get("feedback_type", "other")
        if feedback_type not in FEEDBACK_TYPES:
            feedback_type = "other"

        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()

        type_label = FEEDBACK_TYPES[feedback_type]
        title_preview = message[:60] + ("..." if len(message) > 60 else "")
        issue_title = f"[Feedback] {type_label}: {title_preview}"

        body_parts = [
            f"**Type:** {type_label}",
            "",
        ]
        if name:
            body_parts.append(f"**From:** {name}")
        if email:
            body_parts.append(f"**Email:** {email}")
        if name or email:
            body_parts.append("")

        body_parts.extend([
            "**Message:**",
            "",
            message,
            "",
            "---",
            "*Submitted via the feedback form*",
        ])
        issue_body = "\n".join(body_parts)

        labels = ["feedback"]
        if feedback_type != "other":
            labels.append(feedback_type.replace("_", "-"))

        token = os.environ.get("GITHUB_FEEDBACK_TOKEN")
        if not token:
            self._respond(500, {"success": False, "error": "Server configuration error"})
            return

        success, error = self._create_github_issue(token, issue_title, issue_body, labels)
        if success:
            self._respond(200, {"success": True})
        else:
            self._respond(500, {"success": False, "error": error})

    def _create_github_issue(self, token, title, body, labels):
        payload = json.dumps({
            "title": title,
            "body": body,
            "labels": labels,
        })

        conn = http.client.HTTPSConnection("api.github.com")
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "StatEventsScraping-Feedback",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            conn.request("POST", f"/repos/{GITHUB_REPO}/issues", payload, headers)
            response = conn.getresponse()
            if response.status == 201:
                return True, None
            else:
                resp_body = response.read().decode()
                return False, f"GitHub API error: {response.status}"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    def _respond(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
