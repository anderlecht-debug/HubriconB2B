"""YouTube, unlisted. Self-gated: it refuses anything not marked publishable, which
requires the founder's own recorded voice, a passed QA, and the final sign-off. The
synthetic-media flag is set only when the film shows an AI image."""

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
        return {"status": "blocked", "reason": "not publishable: needs the founder's own recorded takes as its narration, a passed QA, and approve-final"}
    from .qa import PUBLISHABLE_VOICES
    if u.get("voice") not in PUBLISHABLE_VOICES:
        return {"status": "blocked", "reason": "placeholder narration never uploads: record the founder's own takes "
                                               f"(`node content/film/record.mjs {u['slug']}`) and re-run tts"}
    if not TOKEN.exists():
        return {"status": "blocked", "reason": f"YouTube not authorised: put client_secret.json in {SECRETS} and run `hubricon-content youtube-auth` (youtube-token.json)"}
    slug = u["slug"]
    d = scriptmod.video_dir(slug)
    master = d / "media" / "master.mp4"
    desc = (d / "description.md").read_text(encoding="utf-8")
    title = desc.splitlines()[0].strip()[:100]
    from googleapiclient.http import MediaFileUpload
    yt = _service()
    # Synthetic media: the narration is always his own voice, so the flag is set only when an
    # AI image (a Higgsfield texture) is on screen.
    plan = json.loads((d / "shots.json").read_text(encoding="utf-8")) if (d / "shots.json").exists() else {}
    synthetic = any(s.get("kind") == "texture" for s in plan.get("shots", []))
    body = {"snippet": {"title": title, "description": desc[:4900], "categoryId": "27",
                        "tags": ["amazon fba", "ecommerce", "unit economics", "hubricon"]},
            "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": synthetic}}
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
    captions = d / "media" / "captions.srt"
    if captions.exists():   # long films carry YouTube's caption track, nothing burned (VISUAL_SPEC.md §8.6)
        yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "en", "name": "English", "isDraft": False}},
                             media_body=MediaFileUpload(str(captions), mimetype="application/octet-stream")).execute()
    u["youtube_id"] = vid
    (d / "upload.json").write_text(json.dumps({"id": vid, "privacy": "unlisted", "synthetic": synthetic, "title": title,
                                               "captions": captions.exists()}, indent=1) + "\n", encoding="utf-8")
    # Every picture this film used, so none returns within the next ten films (VISUAL_SPEC.md §6.7).
    from .sources import usage as usage_ledger
    ids = [a["id"] for sh in plan.get("shots", []) for a in (sh["asset"] if isinstance(sh.get("asset"), list) else [sh.get("asset")]) if a]
    ids += [sh["params"]["right"]["id"] for sh in plan.get("shots", []) if (sh.get("params") or {}).get("right", {}).get("id")]
    usage_ledger.record_film(slug, ids)
    # The handoff to the site (Part C): the main branch fills a /learn video slot from this.
    (d / "published.json").write_text(json.dumps({"youtube_id": vid, "title": title, "slug": slug, "unit": u.get("id"),
                                                  "src": f"yt-{str(u.get('id') or slug).lower()}"}, indent=1) + "\n", encoding="utf-8")
    return {"status": "ok", "youtube_id": vid, "privacy": "unlisted"}
