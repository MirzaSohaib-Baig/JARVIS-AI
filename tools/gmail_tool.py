import base64
from email.mime.text import MIMEText
from auth.google_auth import get_gmail_service

def send_email(to: str, subject: str, body: str) -> str:
    """Send an email from your Gmail account."""
    service = get_gmail_service()
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return f"Email sent to {to} with subject '{subject}'."


def get_recent_emails(limit: int = 5) -> list[dict]:
    """Get subject lines and senders of the most recent emails in the inbox."""
    service = get_gmail_service()
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
