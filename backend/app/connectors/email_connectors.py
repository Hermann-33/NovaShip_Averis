"""
Email connector layer (adapter-based).

  EMAIL_PROVIDER = none | bundle | gmail | graph
  * GmailConnector  - Gmail API via a user-authorized OAuth refresh token.
                      Primary real provider for inbound and approved outbound email.
  * GraphConnector  - Microsoft 365 / Outlook via Microsoft Graph (client-credentials).
                      Polls a mailbox, downloads attachments (bytes only, never executed),
                      returns normalised message dicts for Pipeline.ingest_email().
  * BundleConnector - local SDOC fixture folder (demo / offline).

Outbound sending (Notifier) is separate and only invoked AFTER human approval.
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build as google_api_build

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

    def send(self, to: list[str], subject: str, body: str, cc: Optional[list[str]] = None) -> dict[str, Any]:  # pragma: no cover - interface
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


class GmailConnector(BaseConnector):
    """Gmail API connector using a one-time user grant and a server-side refresh token."""

    name = "gmail"
    TOKEN_URI = "https://oauth2.googleapis.com/token"
    SCOPES = (
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    )

    def __init__(self) -> None:
        required = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN", "GMAIL_ADDRESS")
        missing = [name for name in required if not os.environ.get(name, "").strip()]
        if missing:
            from app.config import ConfigurationError

            raise ConfigurationError(f"Gmail provider requires {', '.join(missing)}")
        self.client_id = os.environ["GMAIL_CLIENT_ID"].strip()
        self.client_secret = os.environ["GMAIL_CLIENT_SECRET"].strip()
        self.refresh_token = os.environ["GMAIL_REFRESH_TOKEN"].strip()
        self.address = os.environ["GMAIL_ADDRESS"].strip()
        self._credentials: Optional[GoogleCredentials] = None
        self._service = None
        self._token_expires_at = 0.0

    def token(self) -> str:
        if self._credentials and self._credentials.token and time.monotonic() < self._token_expires_at:
            return self._credentials.token
        if self._credentials is None:
            self._credentials = GoogleCredentials(
                token=None,
                refresh_token=self.refresh_token,
                token_uri=self.TOKEN_URI,
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=self.SCOPES,
            )
        self._credentials.refresh(GoogleAuthRequest())
        if not self._credentials.token:
            raise RuntimeError("Gmail OAuth refresh returned no access token")
        lifetime = 3600.0
        if self._credentials.expiry:
            expiry = self._credentials.expiry
            now = datetime.now(expiry.tzinfo) if expiry.tzinfo else datetime.utcnow()
            lifetime = max((expiry - now).total_seconds(), 1.0)
        self._token_expires_at = time.monotonic() + max(lifetime - min(60.0, lifetime * 0.1), 0.0)
        self._service = None
        return self._credentials.token

    def _invalidate_token(self) -> None:
        if self._credentials:
            self._credentials.token = None
            self._credentials.expiry = None
        self._token_expires_at = 0.0
        self._service = None

    def _service_client(self):
        self.token()
        if self._service is None:
            self._service = google_api_build("gmail", "v1", credentials=self._credentials, cache_discovery=False)
        return self._service

    @staticmethod
    def _status_code(exc: Exception) -> Optional[int]:
        response = getattr(exc, "resp", None)
        status = getattr(response, "status", None) or getattr(response, "status_code", None)
        return int(status) if status is not None else None

    def _execute(self, request_factory):
        """Execute a Gmail request, refreshing and retrying exactly once after a 401."""
        for attempt in range(2):
            try:
                return request_factory(self._service_client()).execute()
            except Exception as exc:
                if self._status_code(exc) != 401 or attempt:
                    raise
                self._invalidate_token()
        raise RuntimeError("unreachable")

    def fetch(self, since: Optional[datetime] = None, limit: int = 50) -> Iterable[InboundMessage]:
        if limit <= 0:
            return
        query = None
        if since:
            aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
            query = f"after:{int(aware.timestamp())}"
        listed = self._execute(lambda service: service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=min(limit, 500), q=query
        ))
        for summary in (listed.get("messages") or [])[:limit]:
            message_id = summary["id"]
            message = self._execute(lambda service, mid=message_id: service.users().messages().get(
                userId="me", id=mid, format="full"
            ))
            payload = message.get("payload") or {}
            headers = _gmail_headers(payload)
            from_name, from_address = parseaddr(headers.get("from", ""))
            to = [address for _name, address in getaddresses([headers.get("to", "")]) if address]
            cc = [address for _name, address in getaddresses([headers.get("cc", "")]) if address]
            attachment_parts = [part for part in _gmail_leaf_parts(payload) if part.get("filename")]
            validate_attachment_count(len(attachment_parts))
            blobs: dict[str, bytes] = {}
            paths: list[str] = []
            for part in attachment_parts:
                attachment_body = part.get("body") or {}
                validate_file_size(int(attachment_body.get("size") or 0))
                encoded = attachment_body.get("data")
                if not encoded and attachment_body.get("attachmentId"):
                    attachment = self._execute(
                        lambda service, aid=attachment_body["attachmentId"], mid=message_id:
                        service.users().messages().attachments().get(userId="me", messageId=mid, id=aid)
                    )
                    validate_file_size(int(attachment.get("size") or 0))
                    encoded = attachment.get("data")
                encoded = encoded or ""
                if len(encoded) > ((max_file_bytes() + 2) // 3) * 4 + 4:
                    raise UnsafeUpload("Gmail attachment exceeds maximum size")
                data = _gmail_b64decode(encoded)
                validate_file_size(len(data))
                name = safe_filename(_decoded_header(part.get("filename") or "attachment.bin"))
                path = _unique_attachment_path(name, blobs)
                blobs[path] = data
                paths.append(path)
            message_header_id = headers.get("message-id") or message_id
            raw = {
                "email_id": _safe_id(message_header_id),
                "provider_message_id": message_id,
                "conversation_id": message.get("threadId"),
                "from": from_address,
                "from_name": _decoded_header(from_name) or None,
                "to": to,
                "cc": cc,
                "subject": _decoded_header(headers.get("subject", "")),
                "body": _gmail_message_body(payload),
                "attachments": paths,
            }
            received_at = None
            if message.get("internalDate"):
                received_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=timezone.utc).replace(tzinfo=None)
            yield InboundMessage(raw=raw, blobs=blobs, received_at=received_at, provider="gmail")

    def send(self, to: list[str], subject: str, body: str, cc: Optional[list[str]] = None) -> dict[str, Any]:
        message = EmailMessage()
        message["From"] = self.address
        message["To"] = ", ".join(to)
        if cc:
            message["Cc"] = ", ".join(cc)
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        sent = self._execute(lambda service: service.users().messages().send(userId="me", body={"raw": raw}))
        if not sent.get("id"):
            raise RuntimeError("Gmail API did not return an accepted message id")
        return {"status": 200, "id": sent["id"], "thread_id": sent.get("threadId")}


def get_connector() -> Optional[BaseConnector]:
    provider = os.environ.get("EMAIL_PROVIDER", "none").lower()
    if provider == "none":
        return None
    if provider == "gmail":
        return GmailConnector()
    if provider == "graph":
        return GraphConnector()
    if provider == "bundle":
        from app.config import BUNDLE_DIR

        return BundleConnector(BUNDLE_DIR)
    from app.config import ConfigurationError

    raise ConfigurationError("EMAIL_PROVIDER must be one of: none, bundle, gmail, graph")


def get_outbound_connector(mode: Optional[str] = None) -> Optional[BaseConnector]:
    selected = (mode or os.environ.get("EMAIL_SEND_MODE", "simulate")).strip().lower()
    if selected == "simulate":
        return None
    if selected == "gmail":
        return GmailConnector()
    if selected == "graph":
        return GraphConnector()
    from app.config import ConfigurationError

    raise ConfigurationError("EMAIL_SEND_MODE must be one of: simulate, gmail, graph")


def _decoded_header(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (LookupError, UnicodeDecodeError):
        return value


def _gmail_headers(payload: dict[str, Any]) -> dict[str, str]:
    return {str(item.get("name", "")).lower(): _decoded_header(str(item.get("value", ""))) for item in payload.get("headers", [])}


def _gmail_leaf_parts(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    parts = payload.get("parts") or []
    if not parts:
        yield payload
        return
    for part in parts:
        yield from _gmail_leaf_parts(part)


def _gmail_b64decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded, altchars=b"-_", validate=True)


def _gmail_part_text(part: dict[str, Any]) -> str:
    encoded = (part.get("body") or {}).get("data")
    if not encoded:
        return ""
    data = _gmail_b64decode(encoded)
    content_type = _gmail_headers(part).get("content-type", "")
    charset = "utf-8"
    if "charset=" in content_type.lower():
        charset = content_type.lower().split("charset=", 1)[1].split(";", 1)[0].strip(' \t"\'') or "utf-8"
    try:
        return data.decode(charset, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def _gmail_message_body(payload: dict[str, Any]) -> str:
    plain: list[str] = []
    html: list[str] = []
    for part in _gmail_leaf_parts(payload):
        if part.get("filename"):
            continue
        mime = str(part.get("mimeType", "")).lower()
        text = _gmail_part_text(part)
        if text and mime == "text/plain":
            plain.append(text)
        elif text and mime == "text/html":
            html.append(text)
    return "\n".join(plain).strip() or _strip_html("\n".join(html))


def _unique_attachment_path(name: str, blobs: dict[str, bytes]) -> str:
    path = f"attachments/{name}"
    if path not in blobs:
        return path
    stem, suffix = Path(name).stem, Path(name).suffix
    index = 2
    while f"attachments/{stem}_{index}{suffix}" in blobs:
        index += 1
    return f"attachments/{stem}_{index}{suffix}"


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in {"br", "p", "div", "tr", "li"}:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in {"p", "div", "tr", "li"}:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.text.append(data)


def _strip_html(html: str) -> str:
    import re

    parser = _TextHTMLParser()
    parser.feed(html)
    text = "".join(parser.text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def _safe_id(s: str) -> str:
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s).strip("_")[:120]
