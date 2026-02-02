"""Email parsing utilities."""

from __future__ import annotations

import re


def parse_email_body(body: str) -> str:
    """
    Clean and parse email body text.
    
    Removes HTML tags, extra whitespace, and normalizes line breaks.
    
    Args:
        body: Raw email body content.
        
    Returns:
        Cleaned email text.
    """
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", body)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove common email artifacts
    text = re.sub(r"--+\s*Forwarded message\s*--+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"--+\s*Original message\s*--+", "", text, flags=re.IGNORECASE)

    return text.strip()


def get_email_subject_and_sender(
    subject: str, sender: str
) -> tuple[str, str]:
    """
    Clean and normalize email subject and sender.
    
    Args:
        subject: Raw subject line.
        sender: Raw sender field.
        
    Returns:
        Tuple of (cleaned_subject, cleaned_sender).
    """
    # Clean subject
    cleaned_subject = re.sub(r"^(Re:|Fwd?:|FW:)\s*", "", subject, flags=re.IGNORECASE)
    cleaned_subject = cleaned_subject.strip()

    # Extract sender name from "Name <email@example.com>" format
    match = re.match(r"^\"?([^\"<]+)\"?\s*<?", sender)
    cleaned_sender = match.group(1).strip() if match else sender

    return cleaned_subject, cleaned_sender
