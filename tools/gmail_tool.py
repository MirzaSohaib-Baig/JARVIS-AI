"""
Gmail tool. Requires a one-time OAuth setup — see README.md "Gmail & Calendar setup".
First run will open a browser window asking you to log into your Google account.
"""

import base64
import os
from email.mime.text import MIMEText
from config.settings import settings

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def _get_gmail_service():
    creds = None
    if os.path.exists(settings.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(settings.TOKEN_PATH, settings.SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(settings.CREDENTIALS_PATH, settings.SCOPES)
            creds = flow.run_local_server(port=0)
        with open(settings.TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email from your Gmail account."""
    service = _get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to} with subject '{subject}'."


def get_recent_emails(limit: int = 5) -> list[dict]:
    """Get subject lines and senders of the most recent emails in the inbox."""
    service = _get_gmail_service()
    results = service.users().messages().list(userId="me", maxResults=limit).execute()
    messages = results.get("messages", [])
    output = []
    for msg in messages:
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="metadata", metadataHeaders=["From", "Subject"])
            .execute()
        )
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        output.append({"from": headers.get("From"), "subject": headers.get("Subject")})
    return output


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email on the user's behalf.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body text"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_emails",
            "description": "Get the sender and subject of the user's most recent emails.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

TOOL_FUNCTIONS = {
    "send_email": send_email,
    "get_recent_emails": get_recent_emails,
}
