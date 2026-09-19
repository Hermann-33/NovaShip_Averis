"""
Email connector layer (adapter-based).

  EMAIL_PROVIDER = none | graph | bundle
  * GraphConnector  - Microsoft 365 / Outlook via Microsoft Graph (client-credentials).
                      Polls a mailbox, downloads attachments (bytes only, never executed),
                      returns normalised message dicts for Pipeline.ingest_email().
  * BundleConnector - local SDOC fixture folder (demo / offline).
  * GmailConnector  - stub with the same interface (future).

Outbound sending (Notifier) is separate and only invoked AFTER human approval.
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from app.file_security import UnsafeUpload, max_file_bytes, resolve_bundle_attachment, safe_filename, validate_attachment_count, validate_file_size


@dataclass
class InboundMessage:
    raw: dict[str, Any]                      # {email_id, from, to, cc, subject, body, attachments:[paths], conversation_id, provider_message_id}
    blobs: dict[str, bytes] = field(default_factory=dict)
    received_at: Optional[datetime] = None
    provider: str = "bundle"


class BaseConnector:
    name = "base"

    def fetch(self, since: Optional[datetime] = None, limit: int = 50) -> Iterable[InboundMessage]:  # pragma: no cover - interface
        raise NotImplementedError


class BundleConnector(BaseConnector):
    name = "bundle"

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)

    def fetch(self, since: Optional[datetime] = None, limit: int = 50) -> Iterable[InboundMessage]:
        files = sorted((self.folder / "inbox").glob("email_*.json"))[:limit]
        for p in files:
            raw = json.loads(p.read_text(encoding="utf-8"))
            validate_attachment_count(len(raw.get("attachments", [])))
            blobs = {}
            for attachment_path in raw.get("attachments", []):
                candidate = resolve_bundle_attachment(self.folder, attachment_path)
                if candidate.exists():
                    validate_file_size(candidate.stat().st_size)
                    data = candidate.read_bytes()
                    blobs[attachment_path] = data
            yield InboundMessage(raw=raw, blobs=blobs, provider="bundle")


class GraphConnector(BaseConnector):
    """Microsoft Graph (application permissions: Mail.Read, Mail.Send for outbound).

    Setup (Person 3): Azure Portal > App registrations > New registration
      -> API permissions: Microsoft Graph > Application > Mail.Read (+ Mail.Send) -> Grant admin consent
      -> Certificates & secrets: new client secret  -> MS_CLIENT_SECRET
      -> Overview: Application (client) ID -> MS_CLIENT_ID ; Directory (tenant) ID -> MS_TENANT_ID
      MS_MAILBOX = the shared documentation mailbox UPN.
    """
    name = "graph"
    AUTH = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    GRAPH = "https://graph.microsoft.com/v1.0"

    def __init__(self) -> None:
        self.tenant = os.environ["MS_TENANT_ID"]
        self.client_id = os.environ["MS_CLIENT_ID"]
        self.secret = os.environ["MS_CLIENT_SECRET"]
        self.mailbox = os.environ["MS_MAILBOX"]
        self._token: Optional[str] = None
        self._token_expires_at = 0.0

    def token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        r = httpx.post(self.AUTH.format(tenant=self.tenant), data={
            "client_id": self.client_id, "client_secret": self.secret, "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials",
        }, timeout=30)
        r.raise_for_status()
        payload = r.json()
        self._token = payload["access_token"]
        lifetime = max(int(payload.get("expires_in", 3600)), 1)
        self._token_expires_at = time.monotonic() + max(lifetime - min(60, lifetime * 0.1), 0)
        return self._token

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an authenticated Graph request, refreshing once after a 401."""
        base_headers = dict(kwargs.pop("headers", {}) or {})
        for attempt in range(2):
            headers = dict(base_headers)
            headers["Authorization"] = f"Bearer {self.token()}"
            response = httpx.request(method, url, headers=headers, **kwargs)
            if response.status_code != 401 or attempt:
                response.raise_for_status()
                return response
            self._token = None
            self._token_expires_at = 0.0
        raise RuntimeError("unreachable")

    def _get(self, path: str, **params) -> dict[str, Any]:
        r = self._request("GET", f"{self.GRAPH}{path}", params=params, timeout=60)
        return r.json()

    def fetch(self, since: Optional[datetime] = None, limit: int = 50) -> Iterable[InboundMessage]:
        params: dict[str, Any] = {"$top": limit, "$orderby": "receivedDateTime desc",
                                  "$select": "id,internetMessageId,conversationId,from,toRecipients,ccRecipients,subject,body,receivedDateTime,hasAttachments"}
        if since:
            params["$filter"] = f"receivedDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        data = self._get(f"/users/{self.mailbox}/mailFolders/inbox/messages", **params)
        for m in data.get("value", []):
            blobs: dict[str, bytes] = {}
            paths: list[str] = []
            if m.get("hasAttachments"):
                atts = self._get(f"/users/{self.mailbox}/messages/{m['id']}/attachments").get("value", [])
                validate_attachment_count(len(atts))
                for a in atts:
                    if a.get("@odata.type") != "#microsoft.graph.fileAttachment":
                        continue  # item/reference attachments are not downloaded
                    name = safe_filename(a.get("name", "attachment.bin"))
                    path = f"attachments/{name}"
                    encoded = a.get("contentBytes", "")
                    if len(encoded) > ((max_file_bytes() + 2) // 3) * 4 + 4:
                        raise UnsafeUpload("Graph attachment exceeds maximum size")
                    data = base64.b64decode(encoded, validate=True)
                    validate_file_size(len(data))
                    blobs[path] = data
                    paths.append(path)
            body = m.get("body", {}).get("content", "") or ""
            if m.get("body", {}).get("contentType") == "html":
                body = _strip_html(body)
            raw = {
                "email_id": _safe_id(m.get("internetMessageId") or m["id"]), "provider_message_id": m["id"], "conversation_id": m.get("conversationId"),
                "from": (m.get("from") or {}).get("emailAddress", {}).get("address", ""), "from_name": (m.get("from") or {}).get("emailAddress", {}).get("name"),
                "to": [r["emailAddress"]["address"] for r in m.get("toRecipients", [])], "cc": [r["emailAddress"]["address"] for r in m.get("ccRecipients", [])],
                "subject": m.get("subject", ""), "body": body, "attachments": paths,
            }
            yield InboundMessage(raw=raw, blobs=blobs, received_at=datetime.fromisoformat(m["receivedDateTime"].replace("Z", "+00:00")).replace(tzinfo=None), provider="graph")

    # ---- outbound (only called by Notifier after human approval) ----------
    def send(self, to: list[str], subject: str, body: str, cc: Optional[list[str]] = None) -> dict[str, Any]:
        payload = {"message": {"subject": subject, "body": {"contentType": "Text", "content": body},
                               "toRecipients": [{"emailAddress": {"address": a}} for a in to],
                               "ccRecipients": [{"emailAddress": {"address": a}} for a in (cc or [])]}, "saveToSentItems": True}
        r = self._request("POST", f"{self.GRAPH}/users/{self.mailbox}/sendMail", json=payload, timeout=30)
        return {"status": r.status_code}


class GmailConnector(BaseConnector):  # pragma: no cover - future adapter
    name = "gmail"

    def fetch(self, since: Optional[datetime] = None, limit: int = 50) -> Iterable[InboundMessage]:
        raise NotImplementedError("Gmail adapter: implement with google-api-python-client users.messages.list/get; same InboundMessage shape.")


def get_connector() -> Optional[BaseConnector]:
    provider = os.environ.get("EMAIL_PROVIDER", "none").lower()
    if provider == "graph":
        return GraphConnector()
    if provider == "bundle":
        from app.config import BUNDLE_DIR

        return BundleConnector(BUNDLE_DIR)
    return None


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<(br|p|div|tr)[^>]*>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _safe_id(s: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")[:120]
