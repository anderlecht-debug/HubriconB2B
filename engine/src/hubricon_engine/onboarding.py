"""Client provisioning and onboarding email, in Python so the hourly operator
can do what scripts/new-client.mjs and scripts/invite-user.mjs do by hand:
find-or-create the client, mint a fresh intake link, give them a portal
seat, and send the branded email from Hagen's desk through Resend.

The copy mirrors the JS scripts but leads with the upload page, because
that is the path that needs nobody at Hubricon to lift a finger.
"""

import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from . import notify

TOKEN_LIFETIME_DAYS = 90
INTAKE_BASE_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com")
EXEC_EMAIL = os.environ.get("EXECUTION_EMAIL", "hagen.simmons@hubricon.com")
CALENDLY_URL = os.environ.get("CALENDLY_URL", "https://calendly.com/hubricon/margin-audit")
FROM = os.environ.get("EMAIL_FROM", "Hagen Simmons <hagen.simmons@hubricon.com>")

# The founder's own addresses and the dry-run workspace: never a prospect,
# never a client, never counted.
INTERNAL_DOMAINS = ("hubricon.com", "gethubricon.com", "hubricon.internal")
INTERNAL_EMAILS = {"hagen.hds@gmail.com", "hagend.s25@gmail.com", "hagenhds@gmail.com"}
INTERNAL_NAMES = {"john doe", "jane doe", "dry runner", "test"}


def is_internal(email: str | None, name: str | None = None) -> bool:
    e = (email or "").strip().lower()
    if not e or e in INTERNAL_EMAILS:
        return True
    domain = e.rsplit("@", 1)[-1]
    if domain in INTERNAL_DOMAINS or domain.endswith(".internal") or domain in ("example.com", "test.com"):
        return True
    if (name or "").strip().lower() in INTERNAL_NAMES:
        return True
    return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def mint_token(db, client_id: str, label: str, rotate: bool = True) -> str:
    """Mints an intake link: raw token returned, only its hash stored. With
    rotate (the default) earlier links stop working; a nudge passes False so
    the link in the welcome email keeps working too."""
    if rotate:
        db.rpc("revoke_intake_tokens", {"p_client_id": client_id}).execute()
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = (datetime.now(timezone.utc) + timedelta(days=TOKEN_LIFETIME_DAYS)).isoformat()
    db.rpc("create_intake_token", {
        "p_client_id": client_id, "p_token_hash": token_hash, "p_label": label, "p_expires_at": expires,
    }).execute()
    return token


def ensure_portal_seat(db, client_id: str, email: str) -> str | None:
    """Auth user (magic-link sign-in, no password) linked to the workspace.
    Returns the auth user id, or None if the admin API is unavailable."""
    try:
        existing = None
        page = 1
        while True:
            users = db.auth.admin.list_users(page=page, per_page=200)
            for u in users or []:
                if (u.email or "").lower() == email:
                    existing = u
                    break
            if existing or not users or len(users) < 200:
                break
            page += 1
        if existing:
            user_id = existing.id
        else:
            created = db.auth.admin.create_user({"email": email, "email_confirm": True})
            user_id = created.user.id
        db.table("client_users").upsert(
            {"user_id": user_id, "client_id": client_id, "role": "owner"}, on_conflict="user_id,client_id"
        ).execute()
        return user_id
    except Exception as err:  # portal seat is a nicety on day one; the upload link is what matters
        print(f"  portal seat for {email} not created: {err}")
        return None


def provision(db, email: str, name: str | None = None, company: str | None = None) -> tuple[dict, str, bool]:
    """Find-or-create the client, mint a fresh intake link, seat them in the
    portal. Returns (client, intake_link, created)."""
    email = email.strip().lower()
    rows = db.table("clients").select("*").eq("contact_email", email).execute().data
    created = False
    if rows:
        client = rows[0]
        patch = {}
        if name and not client.get("contact_name"):
            patch["contact_name"] = name
        if company and not client.get("company_name"):
            patch["company_name"] = company
        if patch:
            client = db.table("clients").update(patch).eq("id", client["id"]).execute().data[0]
    else:
        insert = {"contact_email": email, "status": "pending"}
        if name:
            insert["contact_name"] = name
        if company:
            insert["company_name"] = company
        client = db.table("clients").insert(insert).execute().data[0]
        created = True
    token = mint_token(db, client["id"], "audit intake")
    ensure_portal_seat(db, client["id"], email)
    return client, f"{INTAKE_BASE_URL}/intake?t={token}", created


# -- email copy --------------------------------------------------------------

def _first(name: str | None) -> str:
    return (name or "").strip().split(" ")[0] or "there"


def email_spec(kind: str, first_name: str | None, link: str, portal_url: str | None = None) -> dict:
    welcome = f"{INTAKE_BASE_URL}/welcome"
    portal = portal_url or f"{INTAKE_BASE_URL}/portal"
    greeting = f"Hi {_first(first_name)},"
    exports = [
        'Sales & traffic by product — Reports → Business Reports → "Detail Page Sales and Traffic by Child Item". '
        "One file PER MONTH for the last 6 months (this is what lets us model your trend, not just a snapshot).",
        "Fees & SKU economics — Reports → SKU Economics → one file per month, same 6 months.",
        "Advertising — Advertising Console → Measurement & Reporting → Sponsored ads reports → "
        "Sponsored Products / Search term → last 60 days.",
        "Inventory — Reports → Fulfillment → FBA Inventory → today's snapshot.",
        "Your costs — the page has a one-row-per-SKU template (unit cost, freight, packaging, lead time). "
        "Estimates are fine.",
    ]
    if kind == "welcome":
        return {
            "subject": "You're in — 15 minutes of exports and we take it from here",
            "greeting": greeting,
            "blocks": [
                {"p": "Welcome aboard. Everything you need is on one page:"},
                {"button": "Open your welcome page", "url": welcome},
                {"p": "Fastest path, no Seller Central seat required: five exports through your private upload page. "
                      "The models run the moment your last file lands, and your written Profit Teardown is in "
                      "your desk within 24 hours."},
                {"button": "Open your secure upload page", "url": link},
                {"ol": exports},
                {"p": f"Prefer to grant a seat instead? Add {EXEC_EMAIL} under Settings → User Permissions; the "
                      "welcome page shows the exact four permissions. Want to talk it through first? "
                      f"Book 20 minutes: {CALENDLY_URL}"},
                {"p": "Your first month is free. If we don't find you more than we cost, walk away owing nothing."},
            ],
        }
    if kind == "files":
        return {
            "subject": "Your Profit Teardown — 15 minutes of exports and you're done",
            "greeting": greeting,
            "blocks": [
                {"p": "No seat needed — five exports through your private upload page and we're off (no account required):"},
                {"button": "Open your private upload page", "url": link},
                {"ol": exports},
                {"p": "The models run the moment your last file lands — your written Profit Teardown is in your "
                      "desk within 24 hours."},
                {"p": "Your first month is free. If we don't find you more than we cost, walk away owing nothing."},
            ],
        }
    if kind == "nudge":
        return {
            "subject": "15 minutes and your Teardown starts",
            "greeting": greeting,
            "blocks": [
                {"p": "Quick nudge — your models are waiting on your files."},
                {"button": "Open your secure upload page", "url": link},
                {"p": "Five exports, about 15 minutes; the list is on the page. If something's in the way "
                      "(a report you can't find, a seat you'd rather grant instead), reply here and I'll sort it."},
            ],
        }
    if kind == "teardown_ready":
        return {
            "subject": "Your Profit Teardown is ready",
            "greeting": greeting,
            "blocks": [
                {"p": "The models have run on your files. Your written Profit Teardown, Issue No. 001, is in your desk:"},
                {"button": "Open your desk", "url": portal},
                {"p": "Sign in with this email address; the link arrives in seconds and works once."},
                {"p": "Read it, then tell me where you disagree. If you want the plan walked through live, "
                      f"grab 20 minutes: {CALENDLY_URL}"},
            ],
        }
    raise ValueError(f"unknown email kind {kind!r}")


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


_P = 'style="font-size:16px;margin:0 0 20px"'
_SMALL = 'style="font-size:14px;color:#555;margin:0 0 20px"'


def _html_block(b: dict) -> str:
    if "p" in b:
        return f"  <p {_P}>{_esc(b['p'])}</p>"
    if "path" in b:
        return ('  <p style="font-family:Menlo,Consolas,monospace;font-size:14px;background:#f2f2f2;'
                f'padding:10px 14px;margin:0 0 20px">{_esc(b["path"])}</p>')
    if "button" in b:
        return "\n".join([
            '  <p style="margin:0 0 10px">',
            f'    <a href="{_esc(b["url"])}"',
            '       style="display:inline-block;background:#1a1a1a;color:#ffffff;text-decoration:none;'
            'padding:12px 24px;font-size:15px">',
            f"      {_esc(b['button'])}",
            "    </a>",
            "  </p>",
            f'  <p {_SMALL}><a href="{_esc(b["url"])}" style="color:#555;word-break:break-all">{_esc(b["url"])}</a></p>',
        ])
    if "ol" in b:
        items = "\n".join(f'    <li style="margin:0 0 10px">{_esc(i)}</li>' for i in b["ol"])
        return f'  <ol style="font-size:15px;padding-left:22px;margin:0 0 20px">\n{items}\n  </ol>'
    raise ValueError(f"unknown block {b}")


def render_html(spec: dict) -> str:
    parts = [
        '<div style="max-width:520px;margin:0 auto;padding:32px 24px;font-family:Georgia,\'Times New Roman\','
        'serif;color:#1a1a1a;line-height:1.6">',
        '  <p style="font-size:15px;letter-spacing:0.08em;text-transform:uppercase;color:#8a8a8a;margin:0 0 28px">Hubricon</p>',
        f"  <p {_P}>{_esc(spec['greeting'])}</p>",
        *[_html_block(b) for b in spec["blocks"]],
        f"  <p {_P}>Best,</p>",
        '  <p style="font-size:14px;margin:0">Hagen Simmons<br><span style="color:#8a8a8a">Hubricon</span></p>',
        "</div>",
    ]
    return "\n".join(parts)


def _text_block(b: dict) -> str:
    if "p" in b:
        return b["p"]
    if "path" in b:
        return f"  {b['path']}"
    if "button" in b:
        return f"  {b['url']}"
    if "ol" in b:
        return "\n".join(f"{n + 1}. {i}" for n, i in enumerate(b["ol"]))
    raise ValueError(f"unknown block {b}")


def render_text(spec: dict) -> str:
    return "\n\n".join([spec["greeting"], *[_text_block(b) for b in spec["blocks"]], "Best,\nHagen — Hubricon"])


def send(kind: str, to: str, first_name: str | None, link: str, portal_url: str | None = None) -> bool:
    spec = email_spec(kind, first_name, link, portal_url)
    return notify.send_email(to, spec["subject"], render_text(spec), html=render_html(spec),
                             sender=FROM, reply_to=os.environ.get("EMAIL_REPLY_TO", FROM))


def guess_name_parts(full: str | None) -> tuple[str | None, str | None]:
    parts = re.split(r"\s+", (full or "").strip())
    if not parts or not parts[0]:
        return None, None
    return parts[0], (" ".join(parts[1:]) or None)
