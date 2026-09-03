"""The operator: one hourly pass that runs the funnel end to end.

  1. Outbound  — campaign up, leads in, replies triaged and answered (Instantly).
  2. Bookings  — Calendly bookings the cloud routine parsed → client + welcome email.
  3. TEARDOWN  — prospects who replied with the keyword → client + upload page.
  4. Nudges    — clients who haven't uploaded after 3 / 7 days, once each.
  5. Teardown  — new uploads parsed; first successful run → Issue 001 in the
                 desk, report file in storage, "it's ready" email.
  6. Digest    — the PMF scoreboard and anything only a human can do
                 (show up to a call), emailed to the founder once a day.

Everything is idempotent, so an hourly run that finds nothing does nothing.
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from . import db as dbmod
from . import instantly, onboarding, outbound
from .briefing import build_memo, period_deltas
from .notify import email_configured, send_email

PORTAL_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com") + "/portal"
NUDGE_AFTER_DAYS = 3
FILES_AFTER_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return _now().isoformat()


def _parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


class Pass:
    def __init__(self, db, send: bool, dry: bool):
        self.db = db
        self.send = send and not dry
        self.dry = dry
        self.notes: list[str] = []
        self.human: list[str] = []      # things only the founder can do
        self.warnings: list[str] = []

    def say(self, line: str) -> None:
        print(line)
        self.notes.append(line)

    # -- 1. outbound ---------------------------------------------------------
    def outbound(self) -> None:
        if not instantly.configured():
            self.warnings.append("Outbound is OFF: INSTANTLY_API_KEY is not set. Add it in GitHub → Settings → "
                                 "Environments → Production, and the next hourly run starts sending.")
            return
        api = instantly.Instantly()
        try:
            cid, notes = outbound.ensure_campaign(self.db, api, os.environ.get("POSTAL_ADDRESS"), self.dry)
            for n in notes:
                self.say(n)
            if not cid:
                return
            _, notes = outbound.enroll_from_lists(self.db, api, cid, self.dry)
            for n in notes:
                self.say(n)
            _, notes = outbound.enroll_from_supersearch(self.db, api, cid, self.dry)
            for n in notes:
                self.say(n)
            # Reconcile what we believe against what Instantly holds. It only
            # looks at 'queued' rows, so a disqualified prospect is never
            # repaired back into the campaign the prune below just removed it from.
            _, notes = outbound.repair_enrollment(self.db, api, cid, self.dry)
            for n in notes:
                self.say(n)
            # Harvested sellers (crawled on the founder's Mac) wait as 'enriched'
            # until something with the Instantly key pushes them to the list.
            try:
                from .harvest import run as harvest
                harvest.prune(self.db, api, dry=self.dry, log=self.say)  # re-qualified giants come off the list
                harvest.push(self.db, api, dry=self.dry, log=self.say)
                harvest.owners(self.db, api, dry=self.dry, log=self.say)  # the named founder behind each pushed brand
            except Exception as err:  # never let the free channel break the paid one
                self.warnings.append(f"Harvest push: {err}")
            # A prospect marked dq here is still enrolled over there until
            # something with the API key deletes it. This is that something.
            try:
                from . import outreach
                outreach.prune_dq(self.db, api, dry=self.dry, log=self.say)
            except Exception as err:
                self.warnings.append(f"DQ prune: {err}")
            for n in outbound.sync_campaign_leads(self.db, api, cid):
                self.say(n)
            _, notes = outbound.sync_replies(self.db, api, cid, self.dry)
            for n in notes:
                self.say(n)
            _, notes = outbound.send_approved(self.db, api, self.dry)
            for n in notes:
                self.say(n)
            # Always write both, even when they are only an error: a missing
            # key is indistinguishable from a healthy silence, and that is
            # exactly how twenty hours of zero sends went unnoticed.
            summary = outbound.campaign_summary(api, cid)
            outbound.set_state(self.db, "instantly.analytics", {**summary, "as_of": _iso()})
            try:
                h = outbound.health(self.db, api, cid)
                outbound.set_state(self.db, "instantly.health", h)
                for v in h.get("verdicts", []):
                    self.warnings.append(f"Outbound: {v}")
            except Exception as err:  # a diagnostic must never break the pass
                self.warnings.append(f"Outbound health check failed: {err}")
        except instantly.InstantlyError as err:
            self.warnings.append(f"Instantly: {err}")

    # -- 2. bookings ---------------------------------------------------------
    def bookings(self) -> None:
        rows = (self.db.table("bookings").select("*").is_("provisioned_at", "null")
                .order("created_at").execute().data)
        for b in rows:
            email = (b["invitee_email"] or "").strip().lower()
            if b.get("is_test") or onboarding.is_internal(email, b.get("invitee_name")):
                self.db.table("bookings").update({"is_test": True, "provisioned_at": _iso()}).eq("id", b["id"]).execute()
                continue
            # The routine's fit flag is a note for the call, never a reason to
            # turn a booking away: everyone who books gets the welcome + upload
            # link, and the founder sells on the call.
            fit_note = ""
            if b.get("qualified") is False:
                fit_note = (f" Flagged as a stretch fit ({b.get('dq_reason') or 'no reason given'}) "
                            "— this is a call to sell on.")
            if self.dry:
                self.say(f"[dry] would provision {email} from booking {b['id'][:8]}")
                continue
            company = (b.get("answers") or {}).get("company") or (b.get("answers") or {}).get("storefront")
            client, link, created = onboarding.provision(self.db, email, b.get("invitee_name"), company)
            sent = self._touch(client, "welcome", link, force=True)
            self.db.table("bookings").update({
                "client_id": client["id"], "provisioned_at": _iso(),
                "welcome_sent_at": _iso() if sent else None,
            }).eq("id", b["id"]).execute()
            outbound.log_event(self.db, "booking_provisioned", booking_id=b["id"], client_id=client["id"],
                               payload={"created": created, "welcome_sent": sent})
            # make sure any prospect record lines up with the client
            self.db.table("prospects").update({"status": "booked", "client_id": client["id"], "last_event_at": _iso()}) \
                .eq("email", email).execute()
            when = _parse_ts(b.get("starts_at"))
            when_s = when.astimezone().strftime("%a %b %d, %I:%M %p %Z") if when else "time unknown"
            self.human.append(f"Call booked: {b.get('invitee_name') or email} ({b.get('event_type') or 'event'}) "
                              f"at {when_s}. Welcome email {'sent' if sent else 'NOT sent'}; upload link live."
                              f"{fit_note}")
            self.say(f"Provisioned {email} ({'new' if created else 'existing'} client) from a booking.")

    # -- 3. TEARDOWN replies -------------------------------------------------
    def teardown_requests(self) -> None:
        rows = (self.db.table("prospects").select("*").eq("status", "wants_teardown")
                .is_("client_id", "null").execute().data)
        for p in rows:
            email = p["email"]
            if onboarding.is_internal(email):
                continue
            if self.dry:
                self.say(f"[dry] would provision {email} (replied TEARDOWN)")
                continue
            name = " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x) or None
            client, link, created = onboarding.provision(self.db, email, name, p.get("company_name"))
            sent = self._touch(client, "files", link, force=True)
            self.db.table("prospects").update({"client_id": client["id"], "last_event_at": _iso()}).eq("id", p["id"]).execute()
            outbound.log_event(self.db, "teardown_requested", prospect_id=p["id"], client_id=client["id"],
                               payload={"created": created, "files_sent": sent})
            self.say(f"Provisioned {email} from a TEARDOWN reply; upload page {'sent' if sent else 'NOT sent'}.")

    # -- 4. nudges -----------------------------------------------------------
    def nudges(self) -> None:
        clients = self.db.table("clients").select("*").eq("status", "pending").execute().data
        for c in clients:
            email = c["contact_email"]
            if onboarding.is_internal(email):
                continue
            uploads = self.db.table("uploads").select("id").eq("client_id", c["id"]).limit(1).execute().data
            if uploads:
                continue
            touches = {t["kind"]: _parse_ts(t["sent_at"]) for t in
                       self.db.table("client_touches").select("*").eq("client_id", c["id"]).execute().data}
            start = touches.get("welcome") or touches.get("files") or _parse_ts(c["created_at"])
            if not start:
                continue
            age = (_now() - start).days
            if age >= FILES_AFTER_DAYS and "files" not in touches:
                self._reonboard(c, "files")
            elif age >= NUDGE_AFTER_DAYS and "nudge" not in touches:
                self._reonboard(c, "nudge")

    def _reonboard(self, client: dict, kind: str) -> None:
        if self.dry:
            self.say(f"[dry] would send {kind} to {client['contact_email']}")
            return
        token = onboarding.mint_token(self.db, client["id"], f"{kind} link", rotate=False)
        link = f"{onboarding.INTAKE_BASE_URL}/intake?t={token}"
        if self._touch(client, kind, link):
            self.say(f"Sent {kind} email to {client['contact_email']} (no uploads yet).")

    def _touch(self, client: dict, kind: str, link: str, force: bool = False) -> bool:
        if not self.send or not email_configured():
            self.warnings.append(f"{kind} email to {client['contact_email']} not sent: "
                                 + ("--send not given" if not self.send else "RESEND_API_KEY missing"))
            return False
        if not force:
            done = self.db.table("client_touches").select("kind").eq("client_id", client["id"]).eq("kind", kind).execute().data
            if done:
                return False
        ok = onboarding.send(kind, client["contact_email"], client.get("contact_name"), link, PORTAL_URL)
        if ok:
            self.db.table("client_touches").upsert(
                {"client_id": client["id"], "kind": kind, "sent_at": _iso()}, on_conflict="client_id,kind"
            ).execute()
        return ok

    # -- 5. teardown delivery ------------------------------------------------
    def teardowns(self) -> None:
        from . import cli  # lazy: cli imports the world

        clients = self.db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data
        for c in clients:
            if onboarding.is_internal(c["contact_email"]):
                continue
            issued = (self.db.table("briefings").select("id").eq("client_id", c["id"])
                      .eq("issue_number", 1).limit(1).execute().data)
            if issued:
                continue
            pending = self.db.table("uploads").select("id").eq("client_id", c["id"]).eq("status", "uploaded").execute().data
            if pending:
                if self.dry:
                    self.say(f"[dry] would parse {len(pending)} upload(s) for {c['contact_email']}")
                else:
                    parsed, failed = cli._ingest_client(self.db, c)
                    self.say(f"{c['company_name'] or c['contact_email']}: parsed {parsed} upload(s)"
                             + (f", {failed} FAILED" if failed else ""))
                    if failed:
                        self.human.append(f"{failed} upload(s) from {c['contact_email']} failed to parse; "
                                          "see uploads.parse_error.")
            has_data = bool(
                self.db.table("sku_economics").select("id").eq("client_id", c["id"]).limit(1).execute().data
                or self.db.table("asin_traffic").select("id").eq("client_id", c["id"]).limit(1).execute().data
            )
            if not has_data:
                continue
            if self.dry:
                self.say(f"[dry] would run the models and publish Issue 001 for {c['contact_email']}")
                continue
            try:
                self._publish_first_issue(c, cli)
            except Exception as err:  # never let one client's data break the pass
                self.warnings.append(f"Teardown for {c['contact_email']} failed: {err}")
                print(f"  TEARDOWN FAILED for {c['contact_email']}: {err}", file=sys.stderr)

    def _publish_first_issue(self, c: dict, cli) -> None:
        from . import narrate, storage
        from .models.anomaly import summarize as summarize_anomalies
        from .report.html_report import generate

        run_id = cli._run_models(self.db, c, set(cli.ALL_MODELS), 20000, 42)
        cli._draft_for_run(self.db, c, run_id)
        margins = self.db.table("margin_results").select("*").eq("run_id", run_id).execute().data
        elasticity = self.db.table("elasticity_results").select("*").eq("run_id", run_id).execute().data
        first_name = (c.get("contact_name") or "").split(" ")[0]
        company = c["company_name"] or c["contact_email"]
        deltas = period_deltas(margins)
        memo = build_memo(company, first_name, deltas, [], [], elasticity, 0.0, 0, issue_number=1)
        if narrate.available():
            outputs = cli._load_outputs(self.db, run_id)
            try:
                facts = narrate.build_facts(
                    company, first_name, deltas, [], [], 0.0, 0, issue_number=1,
                    health=outputs.get("health"), value=outputs.get("value"), recovery=outputs.get("recovery"),
                    forecast_rows=(outputs.get("forecast") or {}).get("rows"), risk=outputs.get("risk"),
                    anomaly_summary=summarize_anomalies((outputs.get("anomaly") or {}).get("rows") or []),
                    inv_econ=outputs.get("invecon"),
                )
                result = narrate.narrate(facts)
                if result.get("text"):
                    memo = result["text"]
            except Exception as err:
                print(f"  narrated letter skipped: {err}")

        with tempfile.TemporaryDirectory() as tmp:
            path = generate(self.db, c, run_id=run_id, out_dir=tmp)
            report_path = f"reports/{c['id']}/issue-001.html"
            self.db.storage.from_(storage.BUCKET).upload(
                report_path, path.read_bytes(), {"content-type": "text/html", "upsert": "true"})
        self.db.table("briefings").insert({
            "client_id": c["id"], "run_id": run_id, "video_id": None, "memo": memo, "issue_number": 1,
            "report_path": report_path, "title": "Profit Teardown",
            "headline": "Issue No. 001 — your Profit Teardown",
        }).execute()
        sent = self._touch(c, "teardown_ready", PORTAL_URL, force=True)
        outbound.log_event(self.db, "teardown_delivered", client_id=c["id"], payload={"run_id": run_id, "emailed": sent})
        self.db.table("prospects").update({"status": "client", "last_event_at": _iso()}).eq("email", c["contact_email"]).execute()
        self.say(f"Published Issue 001 for {company}; client {'emailed' if sent else 'NOT emailed'}.")
        self.human.append(f"Teardown delivered to {company}. Optional: record a Loom and attach it with "
                          f"`hubricon brief {c['contact_email']} --video <url>`.")

    # -- 6. digest -----------------------------------------------------------
    def scoreboard(self) -> dict:
        try:
            return self.db.rpc("pmf_scoreboard", {}).execute().data or {}
        except Exception as err:
            self.warnings.append(f"scoreboard unavailable: {err}")
            return {}

    def review_queue(self) -> list[dict]:
        return (self.db.table("prospect_messages").select("id, subject, body, prospects(email)")
                .eq("reply_status", "pending_review").execute().data)

    def digest_text(self) -> str:
        s = self.scoreboard()
        lines = ["Hubricon operator digest", ""]
        if s:
            lines += [
                "PMF scoreboard",
                f"  prospects contacted  {s.get('contacted', 0)}   replied {s.get('replied', 0)}   "
                f"interested {s.get('interested', 0)}   unsubscribed {s.get('unsubscribed', 0)}",
                f"  bookings (real)      {s.get('bookings', 0)}   onboarding {s.get('clients_onboarding', 0)}   "
                f"teardowns delivered {s.get('teardowns_delivered', 0)}",
                f"  paid                 {s.get('paid', 0)}   renewed past free month {s.get('renewed', 0)}   "
                f"churned {s.get('churned', 0)}",
                f"  PMF bar: {s.get('pmf_bar_renewed', 3)} renewed → "
                + ("REACHED" if s.get("pmf_reached") else "not yet"),
                "",
            ]
            by_source = s.get("by_source") or {}
            if by_source:
                lines.append("By channel (which of these is actually working)")
                for src, c in sorted(by_source.items(), key=lambda kv: -kv[1].get("total", 0)):
                    lines.append(f"  {src:<16} {c.get('total', 0):>4} on file   "
                                 f"{c.get('contacted', 0):>4} contacted   "
                                 f"{c.get('replied', 0):>3} replied   "
                                 f"{c.get('interested', 0):>3} interested   "
                                 f"{c.get('dq', 0):>4} disqualified")
                lines.append("")
        analytics = outbound.get_state(self.db, "instantly.analytics", {}) or {}
        lines += ["Instantly campaign",
                  "  " + (", ".join(f"{k} {v}" for k, v in analytics.items() if k != "as_of")
                          if analytics else "no analytics recorded yet"), ""]
        # The stall rule. A campaign that exists, is enrolled and has never
        # sent is the single most expensive thing that can go quietly wrong
        # here, so it gets the loudest line in the digest.
        hs = outbound.get_state(self.db, "instantly.health", {}) or {}
        contacted = (analytics.get("contacted_count") or 0) if not analytics.get("error") else 0
        leads = (hs.get("leads") or {}).get("total") or 0
        if leads and not contacted:
            camp = hs.get("campaign") or {}
            lines += [
                f"COLD CAMPAIGN HAS SENT ZERO EMAILS — {leads} leads enrolled, none contacted",
                f"  campaign status {camp.get('status')} ({camp.get('status_name')})",
            ]
            lines += [f"  → {v}" for v in (hs.get("verdicts") or [])[:6]]
            lines += ["  Run `hubricon doctor`, or read operator_state['instantly.health'].", ""]
        try:
            from .harvest import run as harvest
            h = harvest.status(self.db)
            if h["total"]:
                lines += ["Harvest (free seller leads from public pages)",
                          f"  {h['total']} sellers on file — "
                          + ", ".join(f"{k} {v}" for k, v in sorted(h["by_status"].items())), ""]
        except Exception:
            pass
        queue = self.review_queue()
        if queue:
            lines += [f"{len(queue)} repl{'y' if len(queue) == 1 else 'ies'} waiting for a written answer "
                      "(the cloud routine handles these within a few hours):"]
            for q in queue[:10]:
                lines.append(f"  - {q['prospects']['email']}: {(q.get('subject') or '')[:60]}")
            lines.append("")
        if self.human:
            lines += ["Only you can do these:"] + [f"  - {h}" for h in self.human] + [""]
        if self.warnings:
            lines += ["Warnings:"] + [f"  - {w}" for w in self.warnings] + [""]
        if self.notes:
            lines += ["This pass:"] + [f"  {n}" for n in self.notes] + [""]
        lines.append("— Hubricon operator (automated; reply to reach a human)")
        return "\n".join(lines)


def run(send: bool = False, dry: bool = False, digest: bool = False) -> str:
    db = dbmod.connect()
    p = Pass(db, send=send, dry=dry)
    for step in (p.outbound, p.bookings, p.teardown_requests, p.nudges, p.teardowns):
        try:
            step()
        except Exception as err:  # keep going; the digest carries the failure
            p.warnings.append(f"{step.__name__} crashed: {err}")
            print(f"  {step.__name__} CRASHED: {err}", file=sys.stderr)
    text = p.digest_text()
    print("\n" + text)
    if not dry:
        outbound.log_event(db, "operator_pass", payload={
            "notes": p.notes[:50], "warnings": p.warnings[:50], "human": p.human[:50], "digest": digest})
    founder = os.environ.get("FOUNDER_EMAIL")
    if digest and send and not dry:
        if not founder or not email_configured():
            print("\nDigest not emailed: set FOUNDER_EMAIL and RESEND_API_KEY.")
        elif send_email(founder, "Hubricon operator digest", text):
            print(f"\nDigest emailed to {founder}.")
        else:
            print(f"\nDigest NOT emailed to {founder} — see the error above.")
    return text
