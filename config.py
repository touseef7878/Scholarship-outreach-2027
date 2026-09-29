from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASET = BASE_DIR / "data" / "professors.csv"
CV_FILE = BASE_DIR / "attachments" / "Touseef_Ur_Rehman_Academic_CV.pdf"
CREDENTIALS = BASE_DIR / "credentials" / "credentials.json"
TOKEN = BASE_DIR / "credentials" / "token.json"

# Draft creation only. Sending requires changing this manually AND using --send.
ALLOW_SEND = False
DEFAULT_BATCH_SIZE = 5
FOLLOW_UP_DAYS = 7

# Compose scope permits creating and sending drafts/messages.
SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]
