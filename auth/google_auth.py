import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config.settings import settings

_creds = None

def get_credentials():
    global _creds
    if _creds and _creds.valid:
        return _creds
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
    _creds = creds
    return creds

def get_gmail_service():
    return build("gmail", "v1", credentials=get_credentials())

def get_calendar_service():
    return build("calendar", "v3", credentials=get_credentials())