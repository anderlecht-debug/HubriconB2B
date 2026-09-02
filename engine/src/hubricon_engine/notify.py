"""Email delivery for the always-on layer, via Resend's REST API.

Env-gated: without RESEND_API_KEY every send is a silent no-op (alerts
still land in the portal), so the sweep runs fine before email is set up.
ALERT_FROM must be a sender on a domain verified in Resend.
"""

import json
import os
import sys
import urllib.error
import urllib.request


def email_configured() -> bool:
    return bool(os.environ.get("RESEND_API_KEY"))


def send_email(to: str, subject: str, text: str, html: str | None = None,
               sender: str | None = None, reply_to: str | None = None) -> bool:
    key = os.environ.get("RESEND_API_KEY")
    if not key or not to:
        return False
    payload = {
        "from": sender or os.environ.get("ALERT_FROM", "Hubricon <alerts@hubricon.com>"),
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    if reply_to:
        payload["reply_to"] = reply_to
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return 200 <= res.status < 300
    except urllib.error.HTTPError as err:
        # Say why in the log (wrong team's key, unverified sender domain…)
        # instead of failing silently; the sweep itself keeps going.
        body = err.read().decode(errors="replace")[:300]
        print(f"  email to {to} failed: HTTP {err.code} {body}", file=sys.stderr)
        return False
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"  email to {to} failed: {err}", file=sys.stderr)
        return False


def alert_email_body(company: str, alerts: list[dict]) -> str:
    lines = [f"Hubricon watch report for {company}:", ""]
    for a in alerts:
        lines.append(f"[{a['severity'].upper()}] {a['message']}")
        lines.append("")
    lines.append("Full detail in your portal: https://www.hubricon.com/portal")
    lines.append("")
    lines.append("— Hubricon (automated sweep; reply to reach a human)")
    return "\n".join(lines)
