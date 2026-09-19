"""YouTube, unlisted, with the synthetic-media disclosure set. Self-gated: it
refuses anything not marked publishable, which requires the founder's voice,
a passed QA, and the final sign-off."""

import json
from pathlib import Path

from . import script as scriptmod
from .state import CONTENT_DIR

SECRETS = CONTENT_DIR / ".secrets"
CLIENT_SECRET = SECRETS / "client_secret.json"
TOKEN = SECRETS / "youtube-token.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"]


def authorize() -> str:
    if not CLIENT_SECRET.exists():
        return f"put the OAuth client JSON at {CLIENT_SECRET} first (Google Cloud → APIs → Credentials → Desktop app)"
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    SECRETS.mkdir(exist_ok=True)
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return f"token saved to {TOKEN}"


def _service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def run(u: dict, q: dict, force: bool = False) -> dict:
    if not u.get("publishable"):
        return {"status": "blocked", "reason": "not publishable: needs voice == founder (ELEVENLABS_VOICE_ID), a passed QA, and approve-final"}
    if u.get("voice") != "founder":
        return {"status": "blocked", "reason": "placeholder narration never uploads; set ELEVENLABS_VOICE_ID and re-run tts"}
    if not TOKEN.exists():
        return {"status": "blocked", "reason": f"YouTube not authorised: put client_secret.json in {SECRETS} and run `hubricon-content youtube-auth` (youtube-token.json)"}
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    master = d / "media" / "master.mp4"
    desc = (d / "description.md").read_text(encoding="utf-8")
    title = desc.splitlines()[0].strip()[:100]
    from googleapiclient.http import MediaFileUpload
    yt = _service()
    body = {"snippet": {"title": title, "description": desc[:4900], "categoryId": "27",
                        "tags": ["amazon fba", "ecommerce", "unit economics", "hubricon"]},
            "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True}}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(master), chunksize=8 * 1024 * 1024, resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    vid = res["id"]
    thumb = d / "thumbnail.png"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb))).execute()
        except Exception as err:  # a channel without phone verification cannot set custom thumbnails
            (d / "upload-note.md").write_text(f"thumbnail not set: {err}\n", encoding="utf-8")
    u["youtube_id"] = vid
    (d / "upload.json").write_text(json.dumps({"id": vid, "privacy": "unlisted", "synthetic": True, "title": title}, indent=1) + "\n", encoding="utf-8")
    return {"status": "ok", "youtube_id": vid, "privacy": "unlisted"}
