import base64
import mimetypes
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def get_service(credentials_path: Path, token_path: Path, scopes):
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Missing {credentials_path}. Download Desktop OAuth credentials from Google Cloud and place them there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes)
            creds = flow.run_local_server(port=0)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=creds)


def build_message(to_email: str, subject: str, body: str, attachment: Path):
    msg = EmailMessage()
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    if attachment and attachment.exists():
        mime, _ = mimetypes.guess_type(str(attachment))
        maintype, subtype = (mime or "application/octet-stream").split("/", 1)
        msg.add_attachment(
            attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name
        )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def create_draft(service, message_body):
    return service.users().drafts().create(userId="me", body={"message": message_body}).execute()


def send_message(service, message_body):
    return service.users().messages().send(userId="me", body=message_body).execute()
