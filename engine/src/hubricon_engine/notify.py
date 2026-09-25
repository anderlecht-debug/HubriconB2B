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

from . import meter


USER_AGENT = "Hubricon-engine/1.0 (+https://www.hubricon.com)"


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
        headers={"authorization": f"Bearer {key}", "content-type": "application/json",
                 # Cloudflare in front of api.resend.com answers "error 1010"
                 # (HTTP 403) to Python's default user agent, which made every
                 # engine email fail silently. A named client passes.
                 "user-agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            ok = 200 <= res.status < 300
        if ok:
            meter.email()  # a count for the unit economics; never raises, never holds the mail
        return ok
    except urllib.error.HTTPError as err:
        # Say why in the log (wrong team's key, unverified sender domain…)
        # instead of failing silently; the sweep itself keeps going.
        body = err.read().decode(errors="replace")[:300]
        print(f"  email to {to} failed: HTTP {err.code} {body}", file=sys.stderr)
        return False
    except (urllib.error.URLError, TimeoutError) as err:
        print(f"  email to {to} failed: {err}", file=sys.stderr)
        return False


def letter(first_name: str | None, blocks: list[dict]) -> tuple[str, str]:
    """Every client-facing email is the same typeset letter from the founder's
    desk. The onboarding mail always was; the watch report and the decision
    notice used to be plain-text machine output from a different address, which
    is what the client's recurring experience of Hubricon actually looked like."""
    from .onboarding import render_html, render_text
    spec = {"greeting": f"Hi {(first_name or '').strip().split(' ')[0] or 'there'},", "blocks": blocks}
    return render_text(spec), render_html(spec)


def alert_email_body(company: str, alerts: list[dict], first_name: str | None = None,
                     portal_url: str = "https://www.hubricon.com/portal",
                     record_line: str | None = None) -> tuple[str, str]:
    """The weekly watch, as a letter rather than a log dump.

    Severity is said in words, not stamped as [CRITICAL], and the sign-off is a
    person — welcome.html promises "reply to any Hubricon email and it lands
    with the person who builds your models", and this is the email a client
    actually receives most often."""
    n = len(alerts)
    opener = (f"The weekly sweep on {company} finished. "
              + ("One thing needs your eye:" if n == 1 else f"{n} things need your eye:"))
    blocks = [{"p": opener}, {"ol": [
        (("Urgent — " if a.get("severity") == "critical" else "") + a["message"]) for a in alerts
    ]}]
    blocks.append({"p": "The full working is in Hubricon, with the numbers behind each one:"})
    blocks.append({"button": "Open Hubricon", "url": portal_url})
    blocks.append({"p": "Reply to this email if any of it looks wrong — it comes straight to me."})
    if record_line:
        blocks.append({"p": record_line})
    return letter(first_name, blocks)


# Printed once, after the moves, when at least one carries a seal (seal.py).
SEAL_NOTE = ("The seal beside each move is its fingerprint on your Profit Record, taken before this "
             "email was sent. If a promise were changed afterwards it would no longer match its seal, "
             "and your Record export lets anyone check that.")


def directive_email_body(client: dict, directives: list[dict], closes_at, portal_url: str,
                         record_line: str | None = None, seals: dict | None = None) -> tuple[str, str]:
    """The notice terms.html §6 promises: every planned correction, with its
    expected dollars, BEFORE it goes live, and how to stop it.

    Standing-mandate items say the window and what happens at the end of it.
    Explicit ones say plainly that nothing happens without a yes — because
    nothing does.

    `seals` maps a move's id to its short seal, printed beside its expected
    dollars, so the client's own inbox holds a dated copy of what was called.
    A move without one reads exactly as it did before the Seal existed, and
    the note explaining seals appears only when one is printed."""
    standing = [d for d in directives if d.get("mandate") == "standing"]
    explicit = [d for d in directives if d.get("mandate") != "standing"]
    seals = seals or {}

    def line(d):
        usd = d.get("expected_impact_usd")
        parts = [f"expected ${float(usd):,.0f}"] if usd is not None else []
        if seals.get(d.get("id")):
            parts.append(f"seal {seals[d.get('id')]}")
        return d["action_text"] + (f" ({' · '.join(parts)})" if parts else "")

    blocks = [{"p": "Here is what we plan to do next, and what each one is worth. "
                    "Nothing below has happened yet."}]
    if standing:
        when = closes_at.strftime("%A %-d %B at %-I%p").replace("AM", "am").replace("PM", "pm")             if hasattr(closes_at, "strftime") else str(closes_at)
        blocks.append({"p": f"Inside your standing mandate — we go ahead after {when} unless you say no:"})
        blocks.append({"ol": [line(d) for d in standing]})
    if explicit:
        blocks.append({"p": "Outside your mandate — these wait for your explicit yes; after three weeks "
                            "without an answer they lapse and nothing happens:"})
        blocks.append({"ol": [line(d) for d in explicit]})
    # A decline in the portal writes `declined` the moment it is clicked; a reply is
    # read by a person and recorded by hand, so the email must not imply otherwise.
    blocks.append({"p": "Decline any of them in Hubricon and it is recorded the moment you click, "
                        "and that move does not go ahead. A reply to this email reaches Hagen, who "
                        "records it by hand. If this email had not reached you, nothing would move."})
    blocks.append({"button": "Open Hubricon", "url": portal_url})
    blocks.append({"p": "Every one of these lands on your Profit Record afterwards with what it "
                        "actually earned — including the ones that come in under."})
    if any(seals.get(d.get("id")) for d in directives):
        blocks.append({"p": SEAL_NOTE})
    if record_line:
        blocks.append({"p": record_line})
    return letter(client.get("contact_name"), blocks)
