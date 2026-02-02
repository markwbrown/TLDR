"""Gmail API client wrapper."""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from pathlib import Path
from typing import TYPE_CHECKING

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


@dataclass
class EmailMessage:
    """Represents an email message."""

    id: str
    subject: str
    sender: str
    body: str
    raw_message: dict | None = None


@dataclass
class GmailClient:
    """
    Gmail API client for fetching, sending, and managing emails.
    
    Handles OAuth authentication and provides high-level methods
    for common email operations.
    """

    credentials_file: str = "credentials.json"
    token_file: str = "gmail-token.json"
    _service: GmailResource | None = field(default=None, init=False)
    _label_cache: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        """Initialize the Gmail service."""
        self._service = self._authenticate()
        self._load_labels()

    def _authenticate(self) -> GmailResource:
        """Authenticate with Gmail API using OAuth 2.0."""
        creds = None

        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file)

        if not creds or not creds.valid:
            if not os.path.exists(self.credentials_file):
                raise FileNotFoundError(
                    f"Missing {self.credentials_file}. "
                    "Download from Google Cloud Console."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=8537)

            # Save credentials for future runs
            Path(self.token_file).write_text(creds.to_json())
            logger.info(f"Saved credentials to {self.token_file}")

        return build("gmail", "v1", credentials=creds)

    def _load_labels(self) -> None:
        """Cache label name to ID mappings."""
        labels = (
            self._service.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
        )
        self._label_cache = {label["name"]: label["id"] for label in labels}
        logger.debug(f"Loaded {len(self._label_cache)} labels")

    def get_label_id(self, label_name: str) -> str | None:
        """Get label ID by name."""
        return self._label_cache.get(label_name)

    def fetch_messages(self, label: str, max_results: int = 100) -> list[EmailMessage]:
        """
        Fetch messages with the specified label.
        
        Args:
            label: Label name to filter by.
            max_results: Maximum messages to fetch.
            
        Returns:
            List of EmailMessage objects.
        """
        label_id = self.get_label_id(label)
        if not label_id:
            logger.warning(f"Label '{label}' not found")
            return []

        results = (
            self._service.users()
            .messages()
            .list(userId="me", labelIds=[label_id], maxResults=max_results)
            .execute()
        )

        messages = results.get("messages", [])
        logger.info(f"Found {len(messages)} messages with label '{label}'")

        return [self._fetch_message_details(msg["id"]) for msg in messages]

    def _fetch_message_details(self, message_id: str) -> EmailMessage:
        """Fetch full message details."""
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        headers = msg.get("payload", {}).get("headers", [])
        subject = next(
            (h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)"
        )
        sender_full = next(
            (h["value"] for h in headers if h["name"] == "From"), "Unknown"
        )

        # Extract sender name
        import re
        match = re.match(r"^(.*?)<", sender_full)
        sender = match.group(1).strip() if match else sender_full

        body = self._extract_body(msg)

        return EmailMessage(
            id=message_id,
            subject=subject,
            sender=sender,
            body=body,
            raw_message=msg,
        )

    def _extract_body(self, message: dict) -> str:
        """Extract email body from message payload."""
        payload = message.get("payload", {})

        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8")
                elif mime_type == "text/html":
                    data = part.get("body", {}).get("data", "")
                    return base64.urlsafe_b64decode(data).decode("utf-8")
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")

        return ""

    def send_email(self, to: str, subject: str, body: str) -> str:
        """
        Send an email.
        
        Args:
            to: Recipient email address.
            subject: Email subject.
            body: Email body.
            
        Returns:
            Message ID of sent email.
        """
        email = MIMEText(body)
        email["to"] = to
        email["subject"] = subject
        email["from"] = to  # Sending to self

        raw_email = base64.urlsafe_b64encode(email.as_bytes()).decode("utf-8")

        result = (
            self._service.users()
            .messages()
            .send(userId="me", body={"raw": raw_email})
            .execute()
        )

        logger.info(f"Sent email, message ID: {result['id']}")
        return result["id"]

    def modify_labels(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> None:
        """
        Modify labels on a message.
        
        Args:
            message_id: ID of message to modify.
            add_labels: Label names to add.
            remove_labels: Label names to remove.
        """
        add_ids = [self.get_label_id(l) for l in (add_labels or []) if self.get_label_id(l)]
        remove_ids = [self.get_label_id(l) for l in (remove_labels or []) if self.get_label_id(l)]

        body = {
            "addLabelIds": add_ids,
            "removeLabelIds": remove_ids,
        }

        self._service.users().messages().modify(
            userId="me", id=message_id, body=body
        ).execute()

        logger.debug(f"Modified labels on message {message_id}")
