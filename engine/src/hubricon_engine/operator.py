"""The operator: one pass, scheduled hourly, that runs the funnel end to end.

GitHub runs the schedule late, sometimes by hours, so nothing here is ever
promised to a client as "within the hour".

  1. Outbound   — campaign up, leads in, replies triaged and answered
                  (Instantly); cold sending is paused unless switched on.
  2. Bookings   — Calendly bookings the cloud routine parsed → a pending
                  client and the call prep: what the call is, the one thing to
                  do before it, and the optional upload page for a first read.
  3. Replies    — prospects who replied asking for the read → client + upload page.
  4. Nudges     — the agreed letter on the yes, when `hubricon retainer` could
                  not send it; then the upload link again after the call, only
                  where the client's stage allows it (lifecycle.py).
  5. First read — uploads parsed as they land; when the core files are in, or a
                  day after the last upload, Profit Brief No. 001 in Hubricon,
                  the report in storage and the "it's ready" email, and the
                  first moves with it for a client who has said yes.
  6. Billing    — the guarantee month by month; the only code that starts a
                  subscription.
  7. Proof      — every verified dollar becomes a result row; consented rows
                  go public.
  8. Clocks     — export requests built and emailed; exit true-ups counted.
  9. Digest     — the promises the machine cannot keep right now, the PMF
                  scoreboard, speed to value, and anything only a human can
                  do, emailed to the founder daily.

Everything is idempotent, so a pass that finds nothing does nothing.
"""

import os
import re
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

from . import channels
from . import db as dbmod
from . import instantly, onboarding, outbound, proof, referral, speed
from . import meter
from .briefing import build_memo, period_deltas
from .notify import email_configured, send_email

PORTAL_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com") + "/portal"  # mirrors cli.PORTAL_URL
NUDGE_AFTER_DAYS = 3
FILES_AFTER_DAYS = 7
DOWNSELL_AFTER_DAYS = 14     # the smaller door, once, to an Amazon seller whose exports never came
# api/gate.js writes this at the head of fit_notes on a Recovery Only request. The
# site's below-the-bar screen that posted it is gone (2026-09-18); the endpoint stays.
RECOVERY_NOTE = "recovery-only (site gate)"


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
        if outbound.cold_paused():
            self._outbound_paused(api)
            return
        try:
            # The one sentence of record the copy may carry, read here so the
            # campaign PATCHes itself the pass after a result is published.
            try:
                proof_line = proof.line(self.db)
            except Exception as err:
                proof_line = None
                self.warnings.append(f"Proof line unavailable: {err}")
            cid, notes = outbound.ensure_campaign(self.db, api, os.environ.get("POSTAL_ADDRESS"), self.dry,
                                                  proof_line)
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
                outreach.prune_dq(self.db, api, cid, dry=self.dry, log=self.say)
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
            # Teardowns the founder approved, into their own campaign. Its copy
            # is one merge field, so the bytes he read are the bytes that go.
            try:
                from .cold import dispatch as cold_dispatch

                _, notes = cold_dispatch.push(self.db, api, dry=self.dry, log=self.say)
                for n in notes:
                    self.say(n)
            except Exception as err:
                self.warnings.append(f"Teardown dispatch: {err}")
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

    def _outbound_paused(self, api) -> None:
        """Cold is paused (HUBRICON_SPEC.md): nothing is enrolled, pushed, dispatched or
        activated, and any Hubricon campaign still active is paused. The conversations
        already started keep going: replies still sync into triage and the replies the
        founder approved still send."""
        self.say(f"Cold outreach is paused (HUBRICON_SPEC.md, channel decision). Set "
                 f"{outbound.COLD_ENV}=on in the operator's environment to resume.")
        try:
            for n in outbound.hold_campaigns(self.db, api, self.dry):
                self.say(n)
        except instantly.InstantlyError as err:  # the replies below must still sync
            self.warnings.append(f"Could not pause a cold campaign; pause it in Instantly's dashboard: {err}")
        try:
            cid = (outbound.get_state(self.db, "instantly.campaign", {}) or {}).get("id")
            if not cid:
                return
            for n in outbound.sync_campaign_leads(self.db, api, cid):
                self.say(n)
            _, notes = outbound.sync_replies(self.db, api, cid, self.dry)
            for n in notes:
                self.say(n)
            _, notes = outbound.send_approved(self.db, api, self.dry)
            for n in notes:
                self.say(n)
            outbound.set_state(self.db, "instantly.analytics", {**outbound.campaign_summary(api, cid), "as_of": _iso()})
        except instantly.InstantlyError as err:
            self.warnings.append(f"Instantly: {err}")

    # -- 2. bookings ---------------------------------------------------------
    def bookings(self) -> None:
        """Calendly bookings the cloud routine parsed.

        A new address becomes a pending client with an upload link and is sent
        one email, the call prep: what the twenty-minute call is, the one thing
        to do before it, and, second and optional, the upload page for a first
        read before the call. Nothing in it assumes a yes (lifecycle.py). An
        address that is already a client (a kickoff, a reschedule, a second
        booking) is linked and sent nothing, and the founder is told. A call
        prep that did not go out is tried again on later passes while the call
        is still ahead (`_call_prep_retries`); `welcome_sent_at` records the
        one that did."""
        self._prepped: set[str] = set()
        rows = (self.db.table("bookings").select("*").is_("provisioned_at", "null")
                .order("created_at").execute().data)
        for b in rows:
            email = (b["invitee_email"] or "").strip().lower()
            if b.get("is_test") or onboarding.is_internal(email, b.get("invitee_name")):
                self.db.table("bookings").update({"is_test": True, "provisioned_at": _iso()}).eq("id", b["id"]).execute()
                continue
            existing = self.db.table("clients").select("*").eq("contact_email", email).limit(1).execute().data
            if existing:
                self._link_booking(b, existing[0], email)
                continue
            # The routine's fit flag is a note for the call, never a reason to
            # turn a booking away: everyone who books gets the call prep, and
            # the founder sells on the call.
            fit_note = ""
            if b.get("qualified") is False:
                fit_note = (f" Flagged as a stretch fit ({b.get('dq_reason') or 'no reason given'}) "
                            "— this is a call to sell on.")
            if self.dry:
                self.say(f"[dry] would provision {email} from booking {b['id'][:8]} and send the call prep")
                continue
            company = (b.get("answers") or {}).get("company") or (b.get("answers") or {}).get("storefront")
            platform = onboarding.platform_from_answers(b.get("answers"))
            client, link, created = onboarding.provision(self.db, email, b.get("invitee_name"), company, platform)
            self._attribute_booking(client, b, email)
            self.db.table("bookings").update({"client_id": client["id"], "provisioned_at": _iso()}) \
                .eq("id", b["id"]).execute()
            sent = self._send_call_prep(client, b, link)
            outbound.log_event(self.db, "booking_provisioned", booking_id=b["id"], client_id=client["id"],
                               payload={"created": created, "call_prep_sent": sent})
            # make sure any prospect record lines up with the client
            self.db.table("prospects").update({"status": "booked", "client_id": client["id"], "last_event_at": _iso()}) \
                .eq("email", email).execute()
            self.human.append(f"Call booked: {b.get('invitee_name') or email} ({b.get('event_type') or 'event'}) "
                              f"at {self._when(b)}. Call prep email "
                              + ("sent" if sent else "NOT sent (tried again each pass while the call is ahead)")
                              + "; upload link live, optional before the call." + fit_note)
            self.say(f"Provisioned {email} ({'new' if created else 'existing'} client) from a booking.")
        self._call_prep_retries()

    @staticmethod
    def _when(b: dict) -> str:
        when = _parse_ts(b.get("starts_at"))
        return when.astimezone().strftime("%a %b %d, %I:%M %p %Z") if when else "time unknown"

    def _link_booking(self, b: dict, client: dict, email: str) -> None:
        """A booking from an address that is already a client: their kickoff,
        a reschedule, or a second call. They have their upload link and their
        place in the journey; provisioning again would revoke the link, mint
        another and send the first email twice. Link it, tell the founder, send
        nothing. (A client whose call prep never went out is picked up by
        `_call_prep_retries`, for the call this booking now dates.)"""
        from . import lifecycle
        kickoff = bool(onboarding.KICKOFF_EVENT.search(b.get("event_type") or ""))
        if self.dry:
            self.say(f"[dry] would link {'kickoff ' if kickoff else ''}booking {b['id'][:8]} to existing client "
                     f"{email}; nothing sent")
            return
        self.db.table("bookings").update({"client_id": client["id"], "provisioned_at": _iso()}) \
            .eq("id", b["id"]).execute()
        stage = lifecycle.stage_of(self.db, client)
        outbound.log_event(self.db, "kickoff_booked" if kickoff else "booking_linked", booking_id=b["id"],
                           client_id=client["id"], payload={"event_type": b.get("event_type"), "stage": stage})
        who = b.get("invitee_name") or email
        if kickoff:
            self.human.append(f"Kickoff booked: {who} at {self._when(b)}. Existing client, so nothing was sent "
                              "and no new upload link was made.")
        else:
            self.human.append(f"{who} booked again ({b.get('event_type') or 'event'}) for {self._when(b)}: linked "
                              f"to the existing client, stage {stage}. Nothing was sent and the upload link was "
                              "left as it was."
                              + (" They were recorded as declined; if this is a change of mind, the answer is "
                                 "yours to send." if stage == "declined" else ""))
        self.say(f"Linked {'kickoff ' if kickoff else ''}booking for existing client {email}; nothing sent.")

    def _send_call_prep(self, client: dict, b: dict, link: str) -> bool:
        """The call prep, if the stage allows it (the call is still ahead).
        Success is written on the booking, which is what keeps a retry from
        sending it twice even before client_touches can hold the kind."""
        from . import lifecycle
        self._prepped.add(client["id"])
        call = lifecycle.call_at(self.db, client["id"])
        stage = lifecycle.stage(client, call)
        sent = self._touch(client, "call_prep", link, stage=stage, call_at=call)
        if sent:
            self.db.table("bookings").update({"welcome_sent_at": _iso()}).eq("id", b["id"]).execute()
        return sent

    def _prep_sent(self, client_id: str) -> bool:
        """The client was sent their call prep (or, before 2026-10-01, the welcome)."""
        if (self.db.table("bookings").select("id").eq("client_id", client_id)
                .not_.is_("welcome_sent_at", "null").limit(1).execute().data):
            return True
        return bool(self.db.table("client_touches").select("kind").eq("client_id", client_id)
                    .in_("kind", ["call_prep", "welcome"]).limit(1).execute().data)

    def _call_prep_retries(self) -> None:
        """A call prep that did not go out (no mail key, a send that failed) is
        sent on a later pass, once, while the call is still ahead. After the
        call it is never sent: it would describe a call that has happened."""
        from . import lifecycle
        rows = (self.db.table("bookings").select("*").not_.is_("client_id", "null")
                .not_.is_("provisioned_at", "null").is_("welcome_sent_at", "null").execute().data)
        latest: dict[str, dict] = {}
        for b in sorted(rows, key=lambda r: str(r.get("created_at") or "")):
            if b.get("is_test") or onboarding.KICKOFF_EVENT.search(b.get("event_type") or ""):
                continue
            if b["client_id"] not in getattr(self, "_prepped", set()):
                latest[b["client_id"]] = b
        waiting = []
        for cid, b in latest.items():
            got = self.db.table("clients").select("*").eq("id", cid).limit(1).execute().data
            if not got or onboarding.is_internal(got[0]["contact_email"], got[0].get("contact_name")):
                continue
            client = got[0]
            if self._prep_sent(cid) or lifecycle.stage_of(self.db, client) != "booked":
                continue
            waiting.append((client, b))
        if not waiting:
            return
        if self.dry:
            for client, _ in waiting:
                self.say(f"[dry] would send the call prep to {client['contact_email']} (not sent before)")
            return
        if not self.send or not email_configured():
            self.warnings.append(f"{len(waiting)} call prep email(s) waiting to go out: "
                                 + ("--send not given" if not self.send else "RESEND_API_KEY missing")
                                 + ". Each goes on the first pass that can send it, while its call is ahead.")
            return
        for client, b in waiting:
            token = onboarding.mint_token(self.db, client["id"], "call prep link", rotate=False)
            if self._send_call_prep(client, b, f"{onboarding.INTAKE_BASE_URL}/intake?t={token}"):
                self.say(f"Sent the call prep to {client['contact_email']} (it had not gone out before).")

    def _attribute_booking(self, client: dict, b: dict, email: str) -> None:
        """Who sent this booking and what it came from. Never fatal: a booking
        is provisioned whether or not its provenance can be read."""
        try:
            band = proof.revenue_band_from_answers(b.get("answers"))
            if band and not client.get("revenue_band"):
                self.db.table("clients").update({"revenue_band": band}).eq("id", client["id"]).execute()
                client["revenue_band"] = band
        except Exception as err:
            self.warnings.append(f"Revenue band for {email}: {err}")
        try:
            hit = referral.attribute(self.db, client, b)
            if hit and hit.get("matched"):
                who = hit["who"].get("company_name") or hit["who"].get("name") or hit["code"]
                self.say(f"{email} booked on {who}'s link ({hit['matched']}).")
                self.human.append(f"{email} was sent by {who} — say so on the call.")
            elif hit:
                self.warnings.append(f"{email} booked with ref code {hit['code']!r}, which matches nobody.")
        except Exception as err:
            self.warnings.append(f"Referral attribution for {email}: {err}")
        try:
            from . import loop
            tid = loop.attribute_booking(self.db, email, b["id"])
            if tid:
                self.say(f"{email} booked after a teardown ({tid[:8]}).")
        except Exception as err:
            self.warnings.append(f"Teardown attribution for {email}: {err}")

    # -- 3. TEARDOWN replies -------------------------------------------------
    def teardown_requests(self) -> None:
        """The Recovery Only door (api/gate), and what is left of TEARDOWN replies.

        The written Teardown is retired (HUBRICON_SPEC.md: "The Teardown is
        killed … exports are read on or after the call"). A prospect who still
        replies TEARDOWN to an old email is answered by triage with the call and
        the free course, and is moved to 'interested' here: no client row, no
        upload link and no stage-less email before they have even booked."""
        rows = (self.db.table("prospects").select("*").eq("status", "wants_teardown")
                .is_("client_id", "null").execute().data)
        for p in rows:
            email = p["email"]
            if onboarding.is_internal(email):
                continue
            note = p.get("fit_notes") or ""
            recovery = note.startswith(RECOVERY_NOTE)
            if not recovery:
                if self.dry:
                    self.say(f"[dry] would move {email} (replied TEARDOWN) to interested")
                    continue
                self.db.table("prospects").update({"status": "interested", "last_event_at": _iso()}) \
                    .eq("id", p["id"]).execute()
                outbound.log_event(self.db, "teardown_retired", prospect_id=p["id"])
                self.human.append(f"{email} replied TEARDOWN. The Teardown is retired, so they were offered "
                                  "the call and the free course; nothing was provisioned.")
                continue
            if self.dry:
                self.say(f"[dry] would provision {email} (Recovery Only)")
                continue
            name = " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x) or None
            # Recovery Only is Amazon's door; the gate answer says whether
            # the brand also sells on Shopify.
            m = re.search(r"channel:(\w+)", note)
            platform = "both" if m and m.group(1).lower() == "both" else "amazon"
            client, link, created = onboarding.provision(self.db, email, name, p.get("company_name"), platform)
            sent = self._touch(client, "recovery_welcome", link, force=True)
            self.db.table("prospects").update({"client_id": client["id"], "last_event_at": _iso()}).eq("id", p["id"]).execute()
            outbound.log_event(self.db, "recovery_provisioned", prospect_id=p["id"], client_id=client["id"],
                               payload={"created": created, "files_sent": sent})
            self.say(f"Provisioned {email} from a Recovery Only request (api/gate); "
                     f"upload page {'sent' if sent else 'NOT sent'}.")

    # -- 4. nudges -----------------------------------------------------------
    # An email's name in lifecycle.ALLOWED, where the two differ.
    TOUCH_KIND = {"teardown_ready": "first_read", "welcome": "call_prep"}

    def nudges(self) -> None:
        """The upload link again, after the call, to someone with no files in.

        Keyed off the call (lifecycle.call_at), never the booking: the nudge
        three days after it, the export list at seven, and Recovery Only at
        fourteen (Amazon, once). Only where the stage allows each one: a called
        prospect may get all three; a client who said yes and has sent nothing
        gets the first two, counted from the later of the call and the yes, and
        never the downsell. Nothing to anyone who said no or left, and never as
        anyone's first email: a call prep, welcome or agreed letter must have
        gone out first. The agreed letter itself is sent here too, if
        `hubricon retainer` could not send it."""
        from . import lifecycle
        self._agreed_letters()
        clients = self.db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data
        now = _now()
        for c in clients:
            email = c["contact_email"]
            if onboarding.is_internal(email, c.get("contact_name")):
                continue
            uploads = self.db.table("uploads").select("id").eq("client_id", c["id"]).limit(1).execute().data
            if uploads:
                continue
            touches = {t["kind"]: _parse_ts(t["sent_at"]) for t in
                       self.db.table("client_touches").select("*").eq("client_id", c["id"]).execute().data}
            if "recovery_welcome" in touches:
                # They chose the smaller door themselves, below the bar. The
                # export nudges pitch the $6,000 door they were just told the
                # arithmetic rules out, and the day-14 downsell offers the one
                # they came in by; the founder follows up by hand.
                continue
            call = lifecycle.call_at(self.db, c["id"])
            stage = lifecycle.stage(c, call, now)
            if stage not in ("called", "agreed"):
                continue
            if not ({"call_prep", "welcome", "agreed"} & set(touches) or self._prep_sent(c["id"])):
                continue        # never anyone's first email
            start = call
            if stage == "agreed":
                yes = lifecycle.ts(c.get("retainer_started_at"))
                start = max(d for d in (call, yes) if d) if (call or yes) else None
            if not start:
                continue
            age = (now - start).days
            amazon = (c.get("platform") or "amazon") in ("amazon", "both")
            if (age >= DOWNSELL_AFTER_DAYS and "downsell" not in touches and amazon
                    and (c.get("plan") or "retainer") == "retainer" and lifecycle.may_send(stage, "downsell")):
                self._reonboard(c, "downsell", stage=stage)
            elif age >= FILES_AFTER_DAYS and "files" not in touches and lifecycle.may_send(stage, "files"):
                self._reonboard(c, "files", stage=stage)
            elif age >= NUDGE_AFTER_DAYS and "nudge" not in touches and lifecycle.may_send(stage, "nudge"):
                self._reonboard(c, "nudge", stage=stage)

    def _agreed_letters(self) -> None:
        """The letter that confirms a yes, for a client `hubricon retainer`
        could not send it to (no mail key on the founder's machine). Within
        onboarding.AGREED_LETTER_DAYS of the yes only: a confirmation weeks late
        confirms nothing."""
        from . import lifecycle
        rows = (self.db.table("clients").select("*").eq("status", "pending")
                .not_.is_("retainer_started_at", "null").execute().data)
        now = _now()
        for c in rows:
            if onboarding.is_internal(c["contact_email"], c.get("contact_name")):
                continue
            if (c.get("plan") or "retainer") == "recovery" or c.get("retainer_source") == "first_invoice":
                continue
            yes = lifecycle.ts(c.get("retainer_started_at"))
            if not yes or now - yes > timedelta(days=onboarding.AGREED_LETTER_DAYS):
                continue
            if (self.db.table("client_touches").select("kind").eq("client_id", c["id"]).eq("kind", "agreed")
                    .execute().data):
                continue
            if self.dry:
                self.say(f"[dry] would send the agreed letter to {c['contact_email']}")
                continue
            sent, why = onboarding.deliver_agreed(self.db, c, live=self.send)
            if sent:
                self.say(f"Sent the agreed letter to {c['contact_email']}" + ("." if why == "sent" else f": {why}."))
            else:
                self.warnings.append(f"Agreed letter to {c['contact_email']} not sent: {why}.")

    def _reonboard(self, client: dict, kind: str, stage: str | None = None) -> None:
        if self.dry:
            self.say(f"[dry] would send {kind} to {client['contact_email']}")
            return
        if not self._can_send(client, kind):
            return      # no link is minted for an email that cannot go
        token = onboarding.mint_token(self.db, client["id"], f"{kind} link", rotate=False)
        link = f"{onboarding.INTAKE_BASE_URL}/intake?t={token}"
        if self._touch(client, kind, link, stage=stage):
            self.say(f"Sent {kind} email to {client['contact_email']} (no uploads yet).")

    def _can_send(self, client: dict, kind: str) -> bool:
        if not self.send or not email_configured():
            self.warnings.append(f"{kind} email to {client['contact_email']} not sent: "
                                 + ("--send not given" if not self.send else "RESEND_API_KEY missing"))
            return False
        return True

    @meter.metered("onboarding", timed=False)
    def _touch(self, client: dict, kind: str, link: str, force: bool = False, stage: str | None = None,
               **ctx) -> bool:
        """Send one onboarding email, once per kind unless forced.

        With `stage`, the email goes only if lifecycle.may_send allows its kind
        there (TOUCH_KIND maps an email to the lifecycle's name for it). The
        mail goes first and is then recorded; a record the database refuses
        (a kind migration 20261001000003 adds, before it is applied) is a
        warning, never a reason to say the mail did not go."""
        from . import lifecycle
        if stage is not None and not lifecycle.may_send(stage, self.TOUCH_KIND.get(kind, kind)):
            return False
        if not self._can_send(client, kind):
            return False
        if not force:
            done = self.db.table("client_touches").select("kind").eq("client_id", client["id"]).eq("kind", kind).execute().data
            if done:
                return False
        ok = onboarding.send(kind, client["contact_email"], client.get("contact_name"), link, PORTAL_URL,
                             platform=client.get("platform") or "amazon", stage=stage, **ctx)
        if ok:
            try:
                self.db.table("client_touches").upsert(
                    {"client_id": client["id"], "kind": kind, "sent_at": _iso()}, on_conflict="client_id,kind"
                ).execute()
            except Exception as err:
                self.warnings.append(f"{kind} email to {client['contact_email']} went out, but client_touches "
                                     f"would not record it ({str(err)[:120]}). Apply "
                                     f"{onboarding.LIFECYCLE_MIGRATION}.")
        return ok

    # -- 5. the first read ------------------------------------------------------
    def teardowns(self) -> None:
        """The first full read, Profit Brief No. 001, and the first moves with it.

        Uploads are parsed as they land. The read is written when the core
        files for the channel it reads are in (onboarding.CORE_FILES: Amazon's
        Business Report and SKU Economics, Shopify's orders and products), or
        24 hours after the last upload, whichever comes first: a client who
        sends files in pieces gets one read of all of them, and one who stops
        short still gets a read that names what it could not see. Speed is the
        promise, so it is automatic.

        A client who has said yes gets the moves it found in the same pass
        (issue.issue_drafts: sealed, the notice, then the veto window), and one
        whose yes comes after the read gets them on the next pass rather than
        at Monday's sweep. Nobody who has not said yes is sent a move.

        A client on BOTH platforms (2026-10-01) gets one read per platform,
        each run on that platform's rows and saying which it is. The reads wait
        for both platforms' core files (the four lib/intake.js counts), or 24
        hours after the last upload, and then a read is written for each
        platform that has data, in the same pass: Profit Brief No. 001 for
        Amazon and No. 002 for Shopify when both are in. A platform with no
        rows yet gets no read (never an empty Amazon read for a Shopify-only
        upload); its read is written later, when its own core files are in or
        24 hours after its own last upload. Until then every "both" client was
        read once, as Amazon."""
        from . import cli  # lazy: cli imports the world

        clients = self.db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data
        for c in clients:
            if onboarding.is_internal(c["contact_email"], c.get("contact_name")):
                continue
            chans = channels.channels_for(c.get("platform"))
            read = self._first_read_channels(c)
            if read and (len(chans) == 1 or set(chans) <= read):
                self._first_moves_after_yes(c)
                continue
            if read:
                self._later_first_read(c, cli, [ch for ch in chans if ch not in read])
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
            if len(chans) == 1:
                has_data = bool(
                    self.db.table("sku_economics").select("id").eq("client_id", c["id"]).limit(1).execute().data
                    or self.db.table("asin_traffic").select("id").eq("client_id", c["id"]).limit(1).execute().data
                )
            else:
                with_data = [ch for ch in chans if self._channel_has_data(c, ch)]
                has_data = bool(with_data)
            if not has_data:
                continue
            # The clock speed-to-value runs from, set once and never moved:
            # when the first file we could read was uploaded, not when this
            # hourly pass noticed it. Exports pulled through the seat have no
            # upload row and start it on the pass that finds them.
            if not self.dry and speed.set_once(self.db, c, "exports_landed_at", self._first_file_at(c)):
                outbound.log_event(self.db, "exports_landed", client_id=c["id"])
            uploads = (self.db.table("uploads").select("report_type,status,uploaded_at,created_at")
                       .eq("client_id", c["id"]).execute().data)
            ready = self._first_read_ready(uploads, chans, _now())
            if not ready["ready"]:
                waits = ", ".join(onboarding.FILE_GAPS.get(k, (k,))[0] for k in ready["missing"])
                self.say(f"{c['company_name'] or c['contact_email']}: first read waits for {waits}, or until "
                         f"{ready['publish_by'].strftime('%a %b %d %H:%M UTC')} (24 hours after the last upload).")
                continue
            if self.dry:
                self.say(f"[dry] would run the models and publish Issue 001 for {c['contact_email']}"
                         + (f" ({', '.join(channels.label(ch) for ch in with_data)}, one read each)"
                            if len(chans) > 1 else "")
                         + (f" (without {', '.join(ready['missing'])})" if ready["missing"] else ""))
                continue
            try:
                if len(chans) == 1:
                    self._publish_first_issue(c, cli, missing=ready["missing"])
                else:
                    self._publish_first_reads(c, cli, with_data, ready["missing"])
            except Exception as err:  # never let one client's data break the pass
                self.warnings.append(f"First read for {c['contact_email']} failed: {err}")
                print(f"  FIRST READ FAILED for {c['contact_email']}: {err}", file=sys.stderr)

    # -- the first read, per platform ----------------------------------------------
    FIRST_READ_TITLE = "Your first full read"

    def _first_read_channels(self, c: dict) -> set[str]:
        """The platforms this client already has a first read of. Issue 001 is
        one (on the channel its run was computed on); so is any later Brief
        titled as a first read, which is how a "both" client's second platform
        is recorded ("Your first full read · Shopify")."""
        rows = (self.db.table("briefings").select("id, issue_number, title, run_id")
                .eq("client_id", c["id"]).execute().data)
        out = set()
        for r in rows:
            title = str(r.get("title") or "")
            if r.get("issue_number") != 1 and not title.startswith(self.FIRST_READ_TITLE):
                continue
            ch = next((k for k, lab in channels.LABEL.items() if title.endswith(f"· {lab}")), None)
            if ch is None and r.get("run_id"):
                run = (self.db.table("model_runs").select("params").eq("id", r["run_id"]).limit(1).execute().data)
                ch = ((run[0].get("params") or {}).get("channel") if run else None)
            out.add(ch or channels.client_channel(c) or "amazon")
        return out

    def _channel_has_data(self, c: dict, channel: str) -> bool:
        if self.db.table("sku_economics").select("id").eq("client_id", c["id"]).eq("channel", channel) \
                .limit(1).execute().data:
            return True
        return channel == "amazon" and bool(
            self.db.table("asin_traffic").select("id").eq("client_id", c["id"]).limit(1).execute().data)

    @staticmethod
    def _upload_channel(report_type: str | None) -> str | None:
        """The platform an upload belongs to: the parser's CHANNEL, Amazon for
        the parsers that predate the second platform, None for the shared cost
        sheet."""
        from .ingest import PARSERS
        if report_type == "cogs" or report_type not in PARSERS:
            return None
        return getattr(PARSERS[report_type], "CHANNEL", "amazon")

    @staticmethod
    def _first_read_ready(uploads: list[dict], chans: tuple[str, ...] | list[str], now: datetime) -> dict:
        """onboarding.first_read_ready over every platform the client sells on:
        ready when each platform's core files are parsed, or 24 hours after the
        last upload. For one platform it is that function unchanged."""
        if len(chans) == 1:
            return onboarding.first_read_ready(uploads, chans[0], now)
        each = [onboarding.first_read_ready(uploads, ch, now) for ch in chans]
        missing = [k for r in each for k in r["missing"]]
        by = [r["publish_by"] for r in each if r.get("publish_by")]
        return {"ready": all(r["ready"] for r in each), "missing": missing,
                "why": "core" if not missing else ("waited" if all(r["ready"] for r in each) else "waiting"),
                "publish_by": max(by) if by else None}

    def _publish_first_reads(self, c: dict, cli, with_data: list[str], missing: list[str]) -> None:
        """A "both" client's first reads, one per platform with data, in one
        pass: numbered in platform order, one email after the last."""
        core = onboarding.CORE_FILES
        for i, ch in enumerate(with_data):
            others = [x for x in channels.channels_for(c.get("platform")) if x != ch]
            self._publish_first_issue(
                c, cli, missing=[k for k in missing if k in core.get(ch, ())], channel=ch, issue_no=i + 1,
                notify=i == len(with_data) - 1, email_missing=missing,
                siblings={x: (with_data.index(x) + 1 if x in with_data else None) for x in others})

    def _later_first_read(self, c: dict, cli, unread: list[str]) -> None:
        """A "both" client whose first read covered one platform, because the
        other's files had not come: that platform's own first read, once its
        rows are in and its core files are, or 24 hours after its own last
        upload. Numbered as the next Brief; no "first read ready" email, since
        that email names Profit Brief No. 001 (the founder is told instead)."""
        pending = self.db.table("uploads").select("id").eq("client_id", c["id"]).eq("status", "uploaded").execute().data
        if pending and not self.dry:
            parsed, failed = cli._ingest_client(self.db, c)
            self.say(f"{c['company_name'] or c['contact_email']}: parsed {parsed} upload(s)"
                     + (f", {failed} FAILED" if failed else ""))
            if failed:
                self.human.append(f"{failed} upload(s) from {c['contact_email']} failed to parse; "
                                  "see uploads.parse_error.")
        due = [ch for ch in unread if self._channel_has_data(c, ch)]
        uploads = (self.db.table("uploads").select("report_type,status,uploaded_at,created_at")
                   .eq("client_id", c["id"]).execute().data) if due else []
        for ch in due:
            mine = [u for u in uploads if self._upload_channel(u.get("report_type")) == ch]
            ready = onboarding.first_read_ready(mine, ch, _now())
            company = c["company_name"] or c["contact_email"]
            if not ready["ready"]:
                waits = ", ".join(onboarding.FILE_GAPS.get(k, (k,))[0] for k in ready["missing"])
                self.say(f"{company}: the {channels.label(ch)} first read waits for {waits}, or until "
                         f"{ready['publish_by'].strftime('%a %b %d %H:%M UTC')}.")
                continue
            if self.dry:
                self.say(f"[dry] would publish the {channels.label(ch)} first read for {c['contact_email']}")
                continue
            try:
                issue_no = cli._next_issue_number(self.db, c["id"])
                self._publish_first_issue(c, cli, missing=ready["missing"], channel=ch, issue_no=issue_no,
                                          notify=False, siblings={})
                self.human.append(
                    f"{company}: their {channels.label(ch)} first read published as Profit Brief No. "
                    f"{issue_no:03d}. The 'first read ready' email names No. 001 only, so none went: tell them.")
            except Exception as err:  # never let one client's data break the pass
                self.warnings.append(f"{channels.label(ch)} first read for {c['contact_email']} failed: {err}")
                print(f"  FIRST READ FAILED for {c['contact_email']} ({ch}): {err}", file=sys.stderr)
        # a yes after the first read: its moves on the next pass, as for any
        # client (only if nothing was ever issued; Monday's sweep after that)
        self._first_moves_after_yes(c)

    def _first_file_at(self, c: dict) -> datetime | None:
        rows = (self.db.table("uploads").select("uploaded_at").eq("client_id", c["id"]).eq("status", "parsed")
                .not_.is_("uploaded_at", "null").order("uploaded_at").limit(1).execute().data)
        return _parse_ts(rows[0]["uploaded_at"]) if rows else None

    @staticmethod
    def _first_read_letter(memo: str, missing: list[str], stage: str, extra: list[str] | None = None,
                           opening: str | None = None) -> str:
        """Issue 001's letter, told where the client stands and what the read
        could not see. The stock line "Nothing needs your decision this period
        — the watch continues either way" is true of a client mid-service and
        of nobody else here: a prospect has no watch, and a client who said yes
        is about to be sent their first moves.

        `opening` goes straight after the salutation (a two-platform read says
        which platform it is); `extra` paragraphs (where a Shopify read's fees
        came from, what the store's own files show) go before the close."""
        if stage == "agreed":
            nxt = ("Any moves this read found are listed in their own notice, each with its expected dollars, "
                   "before anything in your account changes. Moves inside your standing yes go live when the "
                   "notice's window closes unless you say no; anything else waits for your yes. If the notice "
                   "does not reach you, nothing in it goes live.")
        else:
            nxt = ("Nothing in this read changes anything in your account. Moves are made only after you say yes "
                   "to Managed Profit, and each is listed with its expected dollars before it goes live.")
        stock = "Nothing needs your decision this period — the watch continues either way."
        if opening:
            hello = re.search(r"^Dear [^\n]*,\n", memo, flags=re.M)
            memo = (memo[:hello.end()] + "\n" + opening + "\n" + memo[hello.end():] if hello
                    else opening + "\n\n" + memo)
        add = [x for x in (*(extra or []), onboarding.missing_note(missing), None if stock in memo else nxt) if x]
        memo = memo.replace(stock, nxt)
        if not add:
            return memo
        sign = "\n\n— Hubricon"
        at = memo.rfind(sign)
        block = "\n\n".join(add)
        return memo[:at] + "\n\n" + block + memo[at:] if at >= 0 else memo.rstrip() + "\n\n" + block

    @staticmethod
    def _platform_opening(channel: str, siblings: dict | None) -> str | None:
        """A two-platform client's read names its platform, and where the
        other platform's read is (or that it comes when the files do)."""
        if siblings is None:
            return None
        what = {"amazon": "Amazon account", "shopify": "Shopify store"}
        line = f"This read covers your {what.get(channel, channels.label(channel))} only."
        for other, n in siblings.items():
            line += (f" Your {what.get(other, channels.label(other))} has its own read, Profit Brief No. {n:03d}."
                     if n else f" Your {channels.label(other)} files are not in yet; your "
                               f"{what.get(other, channels.label(other))} gets its own read when they are.")
        return line

    def _shopify_findings(self, c: dict, cli, run_id: str) -> dict | None:
        """What the store's own files show (models/shopify_findings: the
        compare-at discount and the parcel band, each found, not proven),
        saved on the run as `shopify_findings` before the moves are drafted,
        so a drafting pass that reads it (directives.compare_at_directives)
        sees it. Never a reason for the read not to publish."""
        from .models import shopify_findings
        try:
            findings = shopify_findings.run(cli._load_data(self.db, c["id"], "shopify"))
            cli._save_output(self.db, run_id, c["id"], "shopify_findings", findings)
            return findings
        except Exception as err:
            self.warnings.append(f"Shopify findings for {c['contact_email']} skipped: {err}")
            return None

    @staticmethod
    def _shopify_extras(findings: dict | None, margins: list[dict], drafted: list[dict] | None) -> list[str]:
        """A Shopify read's own paragraphs: where its processing fees came from
        (models/margin.fee_basis_line), then the findings in words."""
        from .models import margin as marginmod
        from .models import shopify_findings
        stepped = {(d.get("evidence") or {}).get("sku") for d in drafted or []
                   if d.get("kind") == "price_step" and float((d.get("evidence") or {}).get("step_fraction") or 0) > 0}
        return ([x for x in (marginmod.fee_basis_line(margins),) if x]
                + shopify_findings.letter_paragraphs(findings, stepped))

    @meter.metered("teardown")
    def _publish_first_issue(self, c: dict, cli, missing: list[str] | None = None, channel: str | None = None,
                             issue_no: int = 1, notify: bool = True, email_missing: list[str] | None = None,
                             siblings: dict | None = None) -> None:
        """One first read. For a single-platform client it is Issue 001 as it
        always was; a two-platform client gets one of these per platform
        (`channel`, `issue_no`, `siblings` naming the other platform's read),
        with the email after the last (`notify`)."""
        from . import lifecycle, narrate, storage
        from .models.anomaly import summarize as summarize_anomalies
        from .report.html_report import generate

        missing = list(missing or [])
        both = siblings is not None
        channel = channel or channels.client_channel(c) or "amazon"
        call = lifecycle.call_at(self.db, c["id"])
        stage = lifecycle.stage(c, call)
        run_id = cli._run_models(self.db, c, set(cli.ALL_MODELS), 20000, 42, channel=channel)
        findings = self._shopify_findings(c, cli, run_id) if channel == "shopify" else None
        drafted = cli._draft_for_run(self.db, c, run_id)
        # welcome.html: the 90-day plan is drafted from the first read and
        # presented on the kickoff call. It stays a draft until then.
        cli.draft_plan_for_run(self.db, c, run_id)
        margins = self.db.table("margin_results").select("*").eq("run_id", run_id).execute().data
        elasticity = self.db.table("elasticity_results").select("*").eq("run_id", run_id).execute().data
        first_name = (c.get("contact_name") or "").split(" ")[0]
        company = c["company_name"] or c["contact_email"]
        deltas = period_deltas(margins)
        memo = build_memo(company, first_name, deltas, [], [], elasticity, 0.0, 0, issue_number=issue_no,
                          channel=channel)
        if narrate.available():
            outputs = cli._load_outputs(self.db, run_id)
            try:
                facts = narrate.build_facts(
                    company, first_name, deltas, [], [], 0.0, 0, issue_number=issue_no,
                    health=outputs.get("health"), value=outputs.get("value"), recovery=outputs.get("recovery"),
                    forecast_rows=(outputs.get("forecast") or {}).get("rows"), risk=outputs.get("risk"),
                    anomaly_summary=summarize_anomalies((outputs.get("anomaly") or {}).get("rows") or []),
                    inv_econ=outputs.get("invecon"), data_quality=outputs.get("data_quality"),
                )
                result = narrate.narrate(facts)
                if result.get("text"):
                    memo = result["text"]
            except Exception as err:
                print(f"  narrated letter skipped: {err}")
        extra = self._shopify_extras(findings, margins, drafted) if channel == "shopify" else []
        memo = self._first_read_letter(memo, missing, stage, extra=extra,
                                       opening=self._platform_opening(channel, siblings))

        video_path = None
        with tempfile.TemporaryDirectory() as tmp:
            path = generate(self.db, c, run_id=run_id, out_dir=tmp)
            report_path = f"reports/{c['id']}/issue-{issue_no:03d}.html"
            self.db.storage.from_(storage.BUCKET).upload(
                report_path, path.read_bytes(), {"content-type": "text/html", "upsert": "true"})

            # index.html, welcome.html, terms.html §2 and the portal all promise
            # a recorded walkthrough with the first read. This line used to be
            # `"video_id": None` and a note asking the founder to record a Loom.
            from pathlib import Path as _Path
            from . import video as videomod
            from .briefing import build_beats
            beats = build_beats(company, first_name, deltas, [], [], elasticity, 0.0, 0)
            made = videomod.render(company, issue_no, beats, _Path(tmp) / f"issue-{issue_no:03d}.mp4")
            if made:
                video_path = f"reports/{c['id']}/issue-{issue_no:03d}.mp4"
                self.db.storage.from_(storage.BUCKET).upload(
                    video_path, made.read_bytes(), {"content-type": "video/mp4", "upsert": "true"})

        where = {"amazon": "Amazon account", "shopify": "Shopify store"}.get(channel, channels.label(channel))
        self.db.table("briefings").insert({
            "client_id": c["id"], "run_id": run_id, "video_id": None, "video_path": video_path,
            "memo": memo, "issue_number": issue_no,
            "report_path": report_path,
            "title": self.FIRST_READ_TITLE + (f" · {channels.label(channel)}" if both else ""),
            "headline": (f"Profit Brief No. {issue_no:03d} — your first full read"
                         + (f" of your {where}" if both else "")),
        }).execute()
        speed.set_once(self.db, c, "first_issue_at")
        # `reads` names every read this pass wrote, {channel: issue number}, so a
        # seller on both platforms is told both (onboarding._reads_line)
        reads = ({channel: issue_no, **{x: n for x, n in (siblings or {}).items() if n}} if both else None)
        sent = (self._touch(c, "teardown_ready", PORTAL_URL, force=True, stage=stage, call_at=call,
                            missing=missing if email_missing is None else email_missing,
                            **({"reads": reads} if reads else {}))
                if notify else False)
        outbound.log_event(self.db, "teardown_delivered", client_id=c["id"],
                           payload={"run_id": run_id, "emailed": sent, "video": bool(video_path),
                                    "missing": missing, "stage": stage, "channel": channel,
                                    "issue_number": issue_no})
        self.db.table("prospects").update({"status": "client", "last_event_at": _iso()}).eq("email", c["contact_email"]).execute()
        self.say(f"Published Issue {issue_no:03d} for {company}"
                 + (f" ({channels.label(channel)})" if both else "")
                 + (" with video" if video_path else " (no video — see the warning)")
                 + (f", without {', '.join(missing)}" if missing else "")
                 + (f"; client {'emailed' if sent else 'NOT emailed'}." if notify else "."))
        if not video_path:
            # The copy promises a recorded walkthrough. If the pipeline could
            # not make one, that is a promise outstanding, not a nice-to-have.
            self.warnings.append(
                f"Issue {issue_no:03d} for {company} shipped WITHOUT the recorded walkthrough the site promises. "
                f"Record one now: `hubricon brief {c['contact_email']} --video <url>`.")
        if not notify:
            # a read in a two-platform pass leaves the first moves to the pass's
            # last read; a later platform's read leaves them to its caller
            return
        if stage == "agreed":
            self._issue_first_moves(c)

    def _first_moves_after_yes(self, c: dict) -> None:
        """Issue 001 went out before the yes. Now there is a yes, and nothing
        has ever been issued: the drafts go now, not at Monday's sweep."""
        from . import lifecycle
        if lifecycle.stage(c, None) != "agreed":
            return
        if (self.db.table("directives").select("id").eq("client_id", c["id"])
                .not_.is_("issued_at", "null").limit(1).execute().data):
            return
        if not (self.db.table("directives").select("id").eq("client_id", c["id"]).eq("status", "draft")
                .limit(1).execute().data):
            return
        if self.dry:
            self.say(f"[dry] would issue the first moves to {c['contact_email']} (yes after Issue 001)")
            return
        self._issue_first_moves(c)

    def _issue_first_moves(self, c: dict) -> int:
        """A yes and a first read: the drafted moves, through the one gate there
        is (issue.issue_drafts: the stage, the Seal, the notice, then the veto
        window), on every channel the client sells on. Without a way to send
        the notice nothing is issued: an issued move nobody was told about is
        worse than a draft."""
        from . import issue
        company = c.get("company_name") or c["contact_email"]
        if not self.send or not email_configured():
            self.warnings.append(f"{company} said yes and has a first read, but its first moves stay drafts: "
                                 + ("--send not given" if not self.send else "RESEND_API_KEY missing")
                                 + ". The next pass that can send the notice issues them.")
            return 0
        total = 0
        for channel in channels.channels_for(c.get("platform")):
            try:
                res = issue.issue_drafts(self.db, c, channel, PORTAL_URL, send=True)
            except Exception as err:
                self.warnings.append(f"{company}: first moves on {channels.label(channel)} failed: {err}")
                continue
            if not res["issued"]:
                continue
            total += res["issued"]
            self.say(f"{company}: {res['issued']} first move(s) on {channels.label(channel)} issued, "
                     + ("notice sent, veto window open" if res["notified"]
                        else "notice NOT sent, so none can auto-approve")
                     + f"; seal: {res.get('seal')}.")
            if not res["notified"]:
                self.warnings.append(f"{company}: {res['issued']} first move(s) issued without a notice reaching "
                                     "them, so none can go live on silence. Tell them yourself.")
        if total:
            outbound.log_event(self.db, "first_moves_issued", client_id=c["id"], payload={"issued": total})
        return total

    # -- 6. the day-30 guarantee ---------------------------------------------
    def billing(self) -> None:
        """The guarantee, month by month (billing.py, HUBRICON_SPEC.md "The mechanics").

        When the free months end the subscription starts, trialed to the end of
        the first billed month, so every invoice Stripe raises bills a month that
        has happened. Each one is held at draft and judged against that month's
        own number once the sweep has measured it: above the fee it is sent, at
        or below it is voided unsent and the month is free."""
        from . import billing, cli, value

        if not self._guarantee_schema_ready():
            return
        price_id = os.environ.get("STRIPE_PRICE_ID")
        # past_due too: a failed ACH payment on a month that did not clear is
        # exactly the invoice the gate must void.
        clients = self.db.table("clients").select("*").in_("status", ["pending", "active", "past_due"]).execute().data
        for c in clients:
            if onboarding.is_internal(c["contact_email"], c.get("contact_name")):
                continue
            company = c["company_name"] or c["contact_email"]
            # The smaller door: no retainer, a share of what Amazon paid back,
            # invoiced at month end. Never enters the retainer machinery.
            if (c.get("plan") or "retainer") == "recovery":
                self._recovery_billing(c, cli, billing, value)
                continue
            if c.get("stripe_subscription_id"):
                try:
                    self._month_gate(c, cli, billing)
                except Exception as err:
                    self.warnings.append(f"{company}: the month gate failed: {err}")
                continue
            due, why, first = billing.due_to_start(c)
            if not due:
                continue
            fee = float(c.get("monthly_fee_usd") or 6000.0)
            if self.dry:
                self.say(f"[dry] {company}: {why}; would start billing in arrears from {billing.month_label(first)}")
                continue
            if not (price_id and billing.stripe_configured()):
                self.warnings.append(
                    f"{company}: the free months are over but billing did not start: set STRIPE_SECRET_KEY and "
                    f"STRIPE_PRICE_ID. Nothing is lost: every month is still measured, and the next pass starts it.")
                continue
            try:
                sub = billing.start_billing(c, price_id, first)
            except Exception as err:
                self.warnings.append(f"{company}: the free months are over but Stripe refused the subscription: {err}")
                continue
            self.db.table("clients").update({
                "stripe_subscription_id": sub["id"],
                "stripe_customer_id": sub.get("customer") or c.get("stripe_customer_id"),
                "status": "active", "billing_decided_at": _iso(), "billing_decision": "started",
            }).eq("id", c["id"]).execute()
            cli._send_client_email(self.db, c, "billing_started", sub["id"],
                                   "Your Proving Month is over. From here, a month is billed only if it clears "
                                   f"${fee:,.0f}",
                                   billing.started_email_blocks(first, fee, PORTAL_URL), self.send)
            self.say(f"{company}: billing started in arrears; the first invoice judges {billing.month_label(first)}.")

        # terms §5: the day Managed Profit ends, the Record is checked once more.
        leaving = (self.db.table("clients").select("*").eq("status", "churned")
                   .is_("exit_trued_up_at", "null").execute().data)
        for c in leaving:
            if c.get("stripe_customer_id") and not onboarding.is_internal(c["contact_email"], c.get("contact_name")):
                try:
                    self._exit_true_up(c, cli, billing)
                except Exception as err:
                    self.warnings.append(f"{c['company_name'] or c['contact_email']}: the exit true-up failed: {err}")

    def _guarantee_schema_ready(self) -> bool:
        """The refund and the exit true-up write the columns of migration
        20260925000001 (its late_teardown_month_at column is unused since the
        Teardown was retired on 2026-09-30). Without them a refund could be
        made in Stripe and not recorded, then made again once Stripe's
        idempotency key expired, so the whole pass waits, loudly, rather than
        half-run. Nobody is billed early; somebody may be billed late."""
        try:
            self.db.table("invoices").select("refunded_usd").limit(1).execute()
            self.db.table("clients").select("exit_trued_up_at, exit_refund_usd, late_teardown_month_at") \
                .limit(1).execute()
            return True
        except Exception as err:
            self.warnings.append(f"Billing paused: apply supabase/migrations/20260925000001_guarantee_stack.sql "
                                 f"({str(err)[:100]}). Nothing is billed, sent, voided or refunded until it is.")
            return False

    def _record_months(self, c: dict) -> list[dict]:
        return self.db.table("record_months").select("*").eq("client_id", c["id"]).execute().data

    def _month_gate(self, c: dict, cli, billing) -> None:
        """Every invoice nobody has judged, oldest first, against the month it bills.

        The month is measured before the invoice is decided, always: an invoice
        whose month the sweep has not measured yet waits, held. Then it is sent if
        the month cleared the fee and voided if it did not. An open invoice for a
        month that did not clear is voided, a paid one refunded. The client hears
        either way, in one short letter."""
        from . import monthly
        company = c["company_name"] or c["contact_email"]
        invoices = cli._fetch_invoices(self.db, c["id"])
        pending = billing.unjudged_invoices(invoices, c)
        months = monthly.billing_months(c, date.today())
        rows = None
        # A billed month that a dispute has since taken to the fee or under it is
        # judged again: voided if unpaid, refunded if paid. One still above it stands.
        billed = [i for i in invoices if i.get("gate_decision") == "covered" and i.get("gate_month_index") is not None
                  and i.get("status") in ("open", "paid")]
        if billed:
            rows = self._record_months(c)
            by_index = {m["index"]: m for m in months}
            for inv in billed:
                m = by_index.get(int(inv["gate_month_index"]))
                if m and not billing.month_verdict(rows, m, c)["clears"]:
                    inv["gate_decision"] = None
                    pending.append(inv)
        if not pending:
            return
        rows = rows if rows is not None else self._record_months(c)
        for inv in pending:
            label = f"invoice {inv.get('number') or str(inv.get('stripe_invoice_id'))[:12]}"
            held = inv.get("status") == "draft"
            month = billing.invoice_month(inv, months)
            if month is None:
                v = {"month": None, "fee": float(c.get("monthly_fee_usd") or 6000.0), "total": 0.0,
                     "measured": True, "free": False, "clears": False}
            else:
                v = billing.month_verdict(rows, month, c)
                if not v["free"] and not v["measured"]:
                    continue        # the month is not measured yet; the invoice waits for it
            when = billing.month_label(month) if month else "no month"
            if self.dry:
                self.say(f"[dry] {company}: {label} bills {when}: ${v['total']:,.0f} against ${v['fee']:,.0f} — "
                         f"{'would send it' if v['clears'] else 'would void it, the month is free'}")
                continue
            decided = {"gate_decided_at": _iso(), "gate_value": round(v["total"], 2), "gate_fees": round(v["fee"], 2),
                       "gate_month_index": month["index"] if month else None}
            if v["clears"]:
                patch = {"gate_decision": "covered", **decided}
                if held:
                    if not billing.stripe_configured():
                        self.warnings.append(f"{company}: {label} cleared and is held, and cannot be sent: "
                                             f"STRIPE_SECRET_KEY missing. Nobody is billed until it is.")
                        continue
                    try:
                        sent = billing.release_invoice(inv)
                    except Exception as err:
                        self.warnings.append(f"{company}: {label} cleared but Stripe would not send it: {err}")
                        continue
                    inv["status"] = "open"
                    patch.update({"status": "open", "issued_at": _iso(),
                                  "hosted_invoice_url": (sent or {}).get("hosted_invoice_url") or inv.get("hosted_invoice_url"),
                                  "number": (sent or {}).get("number") or inv.get("number")})
                self.db.table("invoices").update(patch).eq("id", inv["id"]).execute()
                first_clear = not any(i.get("gate_decision") == "covered" for i in invoices if i is not inv)
                cli._send_client_email(self.db, c, "month_cleared", str(inv.get("stripe_invoice_id")),
                                       f"{when}: ${v['total']:,.0f} on your Record against the ${v['fee']:,.0f} fee",
                                       billing.cleared_month_email_blocks(v, PORTAL_URL), self.send)
                if first_clear:
                    # The brand that sent them earns its month at their first standing invoice,
                    # and the stated price of the free month is asked for once, now (terms §9).
                    # proof.py publishes "a month cleared the fee" from this, with consent.
                    self.db.table("clients").update({"billing_decision": "cleared"}).eq("id", c["id"]).execute()
                    self._credit_referrer(c)
                    for kind in ("testimonial", "anonymised_results"):
                        try:
                            self.db.table("consents").upsert(
                                {"client_id": c["id"], "kind": kind}, on_conflict="client_id,kind").execute()
                        except Exception:
                            pass
                inv["gate_decision"] = "covered"
                self.say(f"{company}: {label} — {when} cleared at ${v['total']:,.0f}" + ("; sent." if held else "."))
                continue
            if not billing.stripe_configured():
                self.warnings.append(f"{company}: {label} bills {when}, which did not clear (${v['total']:,.0f} against "
                                     f"${v['fee']:,.0f}), and cannot be voided: STRIPE_SECRET_KEY missing.")
                continue
            try:
                how, refunded = billing.waive_invoice(inv, c)
            except Exception as err:
                self.warnings.append(f"{company}: {label} should be voided but Stripe refused: {err}")
                continue
            if how == "voided":
                inv["status"] = "void"
            else:
                inv["refunded_usd"] = float(inv.get("refunded_usd") or 0) + refunded
            self.db.table("invoices").update({
                "gate_decision": "waived", "gate_note": how, **decided,
                **({"status": "void", "voided_at": _iso()} if how == "voided"
                   else {"refunded_usd": round(inv["refunded_usd"], 2)}),
            }).eq("id", inv["id"]).execute()
            if month is not None:
                cli._send_client_email(self.db, c, "month_unbilled", str(inv.get("stripe_invoice_id")),
                                       f"{when}: ${v['total']:,.0f} on your Record, under the ${v['fee']:,.0f} fee. "
                                       f"No invoice",
                                       billing.unbilled_email_blocks(v, how, PORTAL_URL), self.send)
            self.human.append(f"{company}: {when} measured ${v['total']:,.0f} against the ${v['fee']:,.0f} fee, so "
                              f"{label} was {how}. Worth a look at what the month needed.")
            self.say(f"{company}: {label} {how} — {when} did not clear.")

    EXIT_LETTER = "exit_true_up"      # its client_emails kind: one per client, ever

    def _exit_true_up(self, c: dict, cli, billing) -> None:
        """terms §5: when Managed Profit ends, every billed month is checked once
        more against its own number after disputes, and the client hears once.

        Two halves, each done once. The money: a held draft is for the month in
        progress and is voided unsent; an invoice for a month that no longer
        clears is voided if unpaid and refunded if paid; exit_trued_up_at marks
        it, and a partial failure leaves the marker unset for the next pass to
        finish. Then the exit letter, to every client who said yes and left,
        billed or not (`billing.exit_letter`), logged in client_emails so it is
        never sent twice; a pass that cannot send it leaves it, with the exit
        clock (`hubricon cancel`) open, for the next. Both done, the clock closes."""
        from . import monthly
        company = c.get("company_name") or c["contact_email"]
        invoices = cli._fetch_invoices(self.db, c["id"])
        try:
            rows = self._record_months(c)
        except Exception:
            # Without the measured months no invoice can be judged, and an unjudged
            # invoice would be refunded. Only a client with nothing to judge goes on.
            if any(not billing._is_recovery(i) and i.get("status") in ("draft",) + billing.BILLED_STATUSES
                   for i in invoices):
                raise
            rows = []
        months = monthly.billing_months(c, date.today())
        if not c.get("exit_trued_up_at"):
            drafts = [i for i in invoices if i.get("status") == "draft" and not billing._is_recovery(i)]
            t = billing.exit_true_up(rows, months, invoices, c)
            if self.dry:
                self.say(f"[dry] {company}: exit true-up — {len(t['judged'])} billed month(s); "
                         f"would void {len(drafts) + len(t['voids'])} and refund ${t['refunded']:,.2f}")
                f = billing.facts_from_true_up(t, c)
                self.say(f"[dry] {company}: the exit letter would go to {c.get('contact_email')}: "
                         f"“{billing.exit_subject(f)}”")
                return
            if (drafts or t["voids"] or t["refunds"]) and not billing.stripe_configured():
                self.warnings.append(f"{company} has left and is owed a true-up (${t['gap']:,.0f} on months that "
                                     f"did not clear) that cannot run: STRIPE_SECRET_KEY missing. The exit letter "
                                     f"waits for it.")
                return
            try:
                for inv in drafts + t["voids"]:
                    billing.waive_invoice(inv, c)
                    self.db.table("invoices").update({
                        "status": "void", "voided_at": _iso(), "gate_decision": "waived", "gate_decided_at": _iso(),
                        "gate_note": billing.EXIT_UNSENT_NOTE if inv.get("status") == "draft"
                        else billing.EXIT_VOID_NOTE}).eq("id", inv["id"]).execute()
                for inv, amount in t["refunds"]:
                    billing.refund_invoice(inv, amount, "exit")
                    self.db.table("invoices").update({
                        "refunded_usd": round(float(inv.get("refunded_usd") or 0) + amount, 2)}).eq("id", inv["id"]).execute()
            except Exception as err:
                self.warnings.append(f"{company}: the exit true-up stopped part-way ({err}); the next pass finishes it.")
                return
            stamp = _iso()
            self.db.table("clients").update({"exit_trued_up_at": stamp, "exit_refund_usd": t["refunded"]}) \
                .eq("id", c["id"]).execute()
            c = {**c, "exit_trued_up_at": stamp, "exit_refund_usd": t["refunded"]}
            if t["gap"] > 0:
                self.human.append(f"{company} left with ${t['gap']:,.0f} billed on months that do not clear: voided "
                                  f"${t['voided']:,.0f}, refunded ${t['refunded']:,.2f}.")
            self.say(f"{company}: exit true-up done — billed ${t['billed']:,.0f}, refunded ${t['refunded']:,.2f}.")
            invoices = cli._fetch_invoices(self.db, c["id"])
        elif self.dry:
            if not self._exit_letter_sent(c):
                self.say(f"[dry] {company}: trued up {str(c['exit_trued_up_at'])[:10]}; the exit letter would go to "
                         f"{c.get('contact_email')}.")
            return
        if self._exit_letter(c, cli, billing, rows, months, invoices):
            self._close_exit_clock(c, f"trued up {str(c['exit_trued_up_at'])[:10]}, refunded "
                                      f"${float(c.get('exit_refund_usd') or 0):,.2f}; exit letter sent")

    @staticmethod
    def _day(v) -> date | None:
        ts = _parse_ts(str(v)) if v else None
        return ts.date() if ts else None

    def _exit_letter_sent(self, c: dict) -> bool:
        try:
            return bool(self.db.table("client_emails").select("id").eq("client_id", c["id"])
                        .eq("kind", self.EXIT_LETTER).eq("ref_id", str(c["id"])).limit(1).execute().data)
        except Exception:
            return False

    def _exit_clock_row(self, c: dict) -> dict | None:
        try:
            rows = (self.db.table("data_requests").select("*").eq("client_id", c["id"]).eq("kind", "exit")
                    .is_("closed_at", "null").order("opened_at").execute().data)
        except Exception:
            return None
        return rows[0] if rows else None

    def _close_exit_clock(self, c: dict, outcome: str) -> None:
        try:
            self.db.table("data_requests").update({"closed_at": _iso(), "outcome": outcome}) \
                .eq("client_id", c["id"]).eq("kind", "exit").is_("closed_at", "null").execute()
        except Exception:
            pass        # no clock (migration 20261001000005 not applied): nothing to close

    def _exit_letter(self, c: dict, cli, billing, rows, months, invoices) -> bool:
        """Send the exit letter once. True when it has gone, on this pass or an earlier one."""
        company = c.get("company_name") or c["contact_email"]
        if self._exit_letter_sent(c):
            return True
        if not (self.send and email_configured() and c.get("contact_email")):
            self.say(f"{company}: the exit letter waits for a pass that can send email.")
            return False
        clock = self._exit_clock_row(c) or {}
        left_on = self._day(clock.get("opened_at")) or self._day(c.get("exit_trued_up_at")) or date.today()
        f = billing.exit_facts(rows, months, invoices, c)
        directives = self.db.table("directives").select("*").eq("client_id", c["id"]).execute().data
        subject, blocks = billing.exit_letter(
            f, left_on, self._exit_export(c, cli), billing.watch_lines(rows, directives),
            issued_on=self._day(c.get("exit_trued_up_at")) if f["refunded"] else None,
            refund_due=self._day(clock.get("due_at")), plan=c.get("plan"))
        sent = cli._send_client_email(self.db, c, self.EXIT_LETTER, str(c["id"]), subject, blocks, True)
        if sent or self._exit_letter_sent(c):
            self.say(f"{company}: exit letter sent — “{subject}”.")
            return True
        self.warnings.append(f"{company}: the exit letter did not send; the next pass tries again.")
        return False

    def _exit_export(self, c: dict, cli) -> dict | None:
        """The exit letter's export: stored privately with a seven-day link, or,
        when storage is not there, an export request opened so the letter can
        say it is on its way within one working day (and the digest says who
        has to send it)."""
        from . import storage
        company = c.get("company_name") or c["contact_email"]
        try:
            pub = storage.publish_export(self.db, c["id"], f"exit-{_now().date().isoformat()}",
                                         cli.build_export(self.db, c["id"]), cli.export_filename(c))
            return {"url": pub["url"], "expires_at": pub["expires_at"]}
        except Exception as err:
            self.warnings.append(f"{company}: the export for the exit letter could not be stored ({str(err)[:80]}); "
                                 f"an export request is opened instead.")
        return {"pending": True} if self._open_export_request(c, "Opened with the exit letter") else None

    def _open_export_request(self, c: dict, note: str) -> bool:
        """An open 'access' request for this client, opened if there is none,
        due one working day out (the same rule as public.next_working_day)."""
        try:
            if (self.db.table("data_requests").select("id").eq("client_id", c["id"]).eq("kind", "access")
                    .is_("closed_at", "null").limit(1).execute().data):
                return True
            now = _now()
            due = now + timedelta(days={4: 3, 5: 2, 6: 2}.get(now.weekday(), 1))
            self.db.table("data_requests").insert({
                "client_id": c["id"], "requester_email": c.get("contact_email"), "kind": "access", "note": note,
                "due_at": due.isoformat()}).execute()
            return True
        except Exception as err:
            self.warnings.append(f"{c.get('company_name') or c['contact_email']}: no export request could be "
                                 f"opened ({str(err)[:80]}).")
            return False

    def _recovery_billing(self, c: dict, cli, billing, value) -> None:
        """The recovery-only plan: at month end, one invoice for the share of
        what Amazon actually paid on our claims, and nothing else. Also the way
        back up: when the ledger identifies more than the fee beyond
        reimbursements, the digest says to offer the retainer."""
        company = c["company_name"] or c["contact_email"]
        claims = cli._fetch_claims(self.db, c["id"])
        due = billing.recovery_due(claims, date.today(), share=c.get("recovery_share"))
        try:
            directives = self.db.table("directives").select("*").eq("client_id", c["id"]).execute().data
            ledger = value.compute(c, directives, claims, cli._fetch_invoices(self.db, c["id"]))
            beyond = float((ledger.get("identified_parts") or {}).get("directives") or 0)
            if beyond >= float(c.get("monthly_fee_usd") or value.DEFAULT_MONTHLY_FEE_USD):
                self.human.append(f"{company} is on recovery-only and the ledger identifies ${beyond:,.0f} beyond "
                                  f"reimbursements — offer the retainer.")
        except Exception:
            pass
        if not due:
            return
        if due.get("deferred"):
            self.say(f"{company}: {due['deferred']}.")
            return
        if self.dry:
            self.say(f"[dry] {company}: would invoice ${due['amount']:,.2f} ({due['share'] * 100:.0f}% of "
                     f"${due['recovered']:,.2f} recovered, {due['period_start']}–{due['period_end']})")
            return
        if not billing.stripe_configured():
            self.warnings.append(f"{company}: ${due['amount']:,.2f} of recovery share is due and cannot be invoiced: "
                                 "STRIPE_SECRET_KEY missing. Nothing is lost — the next pass invoices it.")
            return
        try:
            inv = billing.invoice_recovery_share(c, due)
        except Exception as err:
            self.warnings.append(f"{company}: recovery invoice failed: {err}")
            return
        row = self.db.table("recovery_invoices").insert({
            "client_id": c["id"], "period_start": due["period_start"].isoformat(),
            "period_end": due["period_end"].isoformat(), "recovered_usd": due["recovered"],
            "share": due["share"], "amount_usd": due["amount"], "n_claims": due["n_claims"],
            "stripe_invoice_id": inv.get("id"), "hosted_invoice_url": inv.get("hosted_invoice_url"),
        }).execute().data[0]
        self.db.table("recovery_claims").update({"recovery_invoice_id": row["id"]}) \
            .in_("id", [k["id"] for k in due["claims"]]).execute()
        patch = {}
        if not c.get("stripe_customer_id") and inv.get("customer"):
            patch["stripe_customer_id"] = inv["customer"]
        if not c.get("retainer_started_at"):
            patch.update({"retainer_started_at": _iso(), "retainer_source": "first_invoice"})
        if patch:
            self.db.table("clients").update(patch).eq("id", c["id"]).execute()
        cli._send_client_email(self.db, c, "recovery_invoice", str(inv.get("id")),
                               "What Amazon paid back, and our share",
                               billing.recovery_email_blocks(due, inv.get("hosted_invoice_url"), PORTAL_URL), self.send)
        outbound.log_event(self.db, "recovery_invoiced", client_id=c["id"],
                           payload={"amount_usd": due["amount"], "recovered_usd": due["recovered"],
                                    "n_claims": due["n_claims"], "invoice": inv.get("id")})
        self.say(f"{company}: invoiced ${due['amount']:,.2f} — {due['share'] * 100:.0f}% of ${due['recovered']:,.2f} "
                 f"Amazon paid on {due['n_claims']} claim(s).")

    def _credit_referrer(self, c: dict) -> None:
        from . import cli
        company = c.get("company_name") or c["contact_email"]
        try:
            credit = referral.credit_referrer(self.db, c)
        except Exception as err:
            self.warnings.append(f"Referral credit for {company} failed: {err}")
            return
        if not credit:
            return
        if credit.get("partner_id"):
            self.human.append(f"{company} came through a partner ({credit['partner_id'][:8]}) and has "
                              "cleared the gate — pay the partner per the terms you agreed.")
            return
        r = credit["referrer"]
        cli._send_client_email(self.db, r, "referral_credit", c["id"], "Your referral month",
                               credit["blocks"], self.send)
        self.say(f"{r.get('company_name') or r['contact_email']} earned a referral month for {company}: "
                 f"{credit['how']}.")

    # -- 7. proof ----------------------------------------------------------------
    def proof(self) -> None:
        """Every verified dollar becomes a result row; consented rows go public.

        Runs after billing so a gate that cleared this pass is a card this pass.
        Keys off value_total and roi_multiple — never the gate's own bar, which
        counts identified-but-unbanked value and is the right bar for an
        invoice and the wrong one for a claim made to a stranger."""
        from . import cli, value
        clients = self.db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data
        for c in clients:
            if onboarding.is_internal(c["contact_email"], c.get("contact_name")):
                continue
            company = c["company_name"] or c["contact_email"]
            directives = self.db.table("directives").select("*").eq("client_id", c["id"]).execute().data
            claims = cli._fetch_claims(self.db, c["id"])
            if not directives and not claims:
                continue
            ledger = value.compute(c, directives, claims, cli._fetch_invoices(self.db, c["id"]))
            if float(ledger.get("value_total") or 0) > 0 and not self.dry:
                speed.set_once(self.db, c, "first_value_at")
            rows = proof.detect(c, ledger, directives, claims)
            if not rows:
                continue
            if self.dry:
                self.say(f"[dry] would record {len(rows)} result(s) for {company}")
                continue
            n = proof.record(self.db, rows)
            if n:
                self.say(f"Recorded {n} result(s) for {company}.")
                if not c.get("industry"):
                    self.human.append(f"{company} has a verified result and no industry word, so it cannot be "
                                      f"published: `hubricon proof set {c['contact_email']} --industry <word>`.")
        if not self.dry:
            published = proof.publish(self.db)
            if published:
                self.say(f"Published {published} consented result(s); the campaign copy follows next pass.")

    def data_requests(self) -> None:
        """Legal clocks, surfaced before they run out, and two the machine keeps itself.

        privacy.html gives a number of days for each of these. Nothing counted
        them, so the only alarm was the requester following up.

        An export request (terms §11: delivered within one working day) is
        fulfilled here: the zip is built, stored in the private 'exports'
        bucket, and a seven-day link goes to the client's own contact email,
        never anyone else's. If any step fails the request stays open and the
        founder is told to run `hubricon export`. An exit (terms §5: a refund
        owed is issued within seven days of the client's email) is the clock
        `hubricon cancel` starts: named here while it runs, closed once the
        true-up is done and the exit letter has gone."""
        from . import billing, cli
        try:
            rows = (self.db.table("data_requests").select("*").is_("closed_at", "null")
                    .order("due_at").execute().data)
        except Exception:
            return      # table not migrated yet
        now = _now()
        for r in rows:
            if r.get("kind") == "exit":
                try:
                    self._exit_clock(r, now, cli, billing)
                except Exception as err:
                    self.warnings.append(f"exit clock {r['id'][:8]} failed: {err}")
                continue
            if r.get("kind") == "access":
                try:
                    if self._fulfil_export(r, cli):
                        continue
                except Exception as err:
                    self.warnings.append(f"export request {r['id'][:8]} failed: {err}")
            left = (datetime.fromisoformat(str(r["due_at"])) - now).days
            who = r.get("requester_email") or "—"
            if left < 0:
                self.warnings.append(f"OVERDUE by {abs(left)}d: {r['kind']} request from {who} "
                                     f"({r['id'][:8]}). The privacy policy gives a deadline; this is past it.")
            elif r.get("opened_at") and (now - datetime.fromisoformat(str(r["opened_at"]))).total_seconds() < 86400:
                # A request is named the day it is opened, not only in the two days
                # before its clock runs out. An export the machine could not send
                # is the founder's to run.
                self.human.append(f"New {r['kind']} request from {who} — due in {left}d ({r['id'][:8]})."
                                  + (" Run: hubricon export <client>" if r["kind"] == "access" else ""))
            elif left <= 2:
                self.human.append(f"{r['kind']} request from {who} is due in {left}d ({r['id'][:8]}).")

    def _client_row(self, client_id) -> dict | None:
        if not client_id:
            return None
        rows = self.db.table("clients").select("*").eq("id", client_id).execute().data
        return rows[0] if rows else None

    def _export_emailed(self, c: dict, r: dict) -> bool:
        try:
            return bool(self.db.table("client_emails").select("id").eq("client_id", c["id"])
                        .eq("kind", "export_ready").eq("ref_id", str(r["id"])).limit(1).execute().data)
        except Exception:
            return False

    def _fulfil_export(self, r: dict, cli) -> bool:
        """terms §11, kept by the machine: build the client's zip, store it in the
        private bucket, email a seven-day link to their contact email, close the
        request. True when the request needs nothing more from the founder this
        pass; False leaves it to the digest's instruction (no client on it, no
        email key, storage not there, the email refused)."""
        from . import storage
        c = self._client_row(r.get("client_id"))
        if not c or not c.get("contact_email"):
            return False
        company = c.get("company_name") or c["contact_email"]
        if self.dry:
            self.say(f"[dry] {company}: would build the export, store it privately and email a "
                     f"{storage.EXPORT_LINK_DAYS}-day link to {c['contact_email']}.")
            return True
        if not self._export_emailed(c, r):
            if not (self.send and email_configured()):
                return False
            try:
                blob = cli.build_export(self.db, c["id"])
                pub = storage.publish_export(self.db, c["id"], str(r["id"]), blob, cli.export_filename(c))
            except Exception as err:
                self.warnings.append(f"{company}: the export could not be stored ({str(err)[:80]}), so the request "
                                     f"waits for `hubricon export` by hand.")
                return False
            sent = cli._send_client_email(self.db, c, "export_ready", str(r["id"]), "Your Profit Record export",
                                          self._export_letter(c, pub), True)
            if not sent and not self._export_emailed(c, r):
                self.warnings.append(f"{company}: the export is stored but its email did not go; the next pass "
                                     f"tries again.")
                return False
            self.say(f"{company}: export emailed to {c['contact_email']} ({len(blob) / 1_000_000:.1f} MB, link "
                     f"good to {pub['expires_at']:%b %-d}).")
        self.db.table("data_requests").update({
            "closed_at": _iso(),
            "outcome": f"emailed a {storage.EXPORT_LINK_DAYS}-day download link to {c['contact_email']}"}) \
            .eq("id", r["id"]).execute()
        return True

    @staticmethod
    def _export_letter(c: dict, pub: dict) -> list[dict]:
        company = c.get("company_name") or "your brand"
        return [
            {"p": f"Here is everything we hold on {company}, as you asked: the exports you sent, every table we "
                  f"computed from them, your whole Profit Record, and the seal file with the verifier that lets "
                  f"anyone check it."},
            {"button": "Download your export", "url": pub["url"]},
            {"p": f"The link works for seven days, until {pub['expires_at']:%B %-d}, and anyone holding it can "
                  f"download the file, so forward it with care. MANIFEST.txt in the zip lists every file, and "
                  f"HOW-TO-VERIFY.txt says how to check your Record yourself."},
            {"p": "When the link runs out, ask again any day, in Hubricon or by replying here, and a fresh one is "
                  "made. It is always free."},
        ]

    def _exit_clock(self, r: dict, now: datetime, cli, billing) -> None:
        """One open exit (terms §5). A client never billed has no Stripe step, so
        the true-up and the exit letter run from here; a billed client's money
        is the billing pass's (it ran earlier this pass, and warned if it could
        not), and a letter that could not go then goes from here. While the
        clock runs the digest names it, with the refund it owes."""
        c = self._client_row(r.get("client_id"))
        if c is None:
            self.warnings.append(f"An exit clock ({r['id'][:8]}) names no client on file; close it with "
                                 f"`hubricon request close {r['id'][:8]} --outcome …`.")
            return
        if onboarding.is_internal(c["contact_email"], c.get("contact_name")):
            return
        company = c.get("company_name") or c["contact_email"]
        if not c.get("exit_trued_up_at") and c.get("stripe_customer_id"):
            pass        # the billing pass owns a billed client's money
        elif c.get("exit_trued_up_at") and self._exit_letter_sent(c):
            self._close_exit_clock(c, f"trued up {str(c['exit_trued_up_at'])[:10]}; exit letter sent")
            return
        else:
            self._exit_true_up(c, cli, billing)
            c = self._client_row(c["id"]) or c
            if c.get("exit_trued_up_at") and self._exit_letter_sent(c):
                return          # closed by _exit_true_up
        due = datetime.fromisoformat(str(r["due_at"]).replace("Z", "+00:00"))
        opened = self._day(r.get("opened_at"))
        who = f"{company} left" + (f" on {opened:%b %-d}" if opened else "")
        if c.get("exit_trued_up_at"):
            # The money is done, so the terms' clock is kept; only the letter is still to go.
            (self.warnings.append if due < now else self.say)(
                f"{who}: trued up {str(c['exit_trued_up_at'])[:10]}, and the exit letter has not gone yet.")
            return
        owed = billing.exit_refund_owed(self._record_months(c), cli._fetch_invoices(self.db, c["id"]), c)
        what = f"${owed:,.2f} to refund" if owed else "the true-up"
        if due < now:
            self.warnings.append(f"OVERDUE by {(now - due).days}d: {who}; {what} was due by {due:%b %-d}. Terms §5: "
                                 f"a refund is issued within seven days of their email.")
        else:
            self.say(f"{who}: {what} due by {due:%b %-d} ({(due - now).days}d left).")

    def promises(self) -> None:
        """Every promise the machine cannot currently keep, in the daily digest.

        A missing secret makes a promise fail quietly — the client simply does
        not get the thing the site says they get. This is the line that stops
        that being discovered by the client."""
        from . import cli
        try:
            rows = cli.promise_rows(self.db)
        except Exception as err:
            self.warnings.append(f"promise check failed: {err}")
            return
        for promise, where, ok, detail in rows:
            if not ok:
                self.warnings.append(f"PROMISE NOT KEPT — {promise} ({where}): {detail}")

    # -- 7. digest -----------------------------------------------------------
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
            from . import loop
            lines += loop.digest_lines(s)
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
        try:
            roster = [c for c in self.db.table("clients").select("*").in_("status", ["pending", "active"])
                      .execute().data if not onboarding.is_internal(c["contact_email"], c.get("contact_name"))]
            if roster:
                lines += speed.digest_lines(roster) + [""]
        except Exception:
            pass
        queue = self.review_queue()
        if queue:
            lines += [f"{len(queue)} repl{'y' if len(queue) == 1 else 'ies'} waiting for a written answer "
                      "(the cloud routine handles these within a few hours):"]
            for q in queue[:10]:
                lines.append(f"  - {q['prospects']['email']}: {(q.get('subject') or '')[:60]}")
            lines.append("")
        # The notes and Briefs the machine drafted and only the founder sends
        # (approval.py; HUBRICON_SPEC.md, "Customer experience" 4).
        try:
            from . import approval
            lines += approval.digest_lines(self.db)
        except Exception as err:
            lines += [f"Waiting for your approval: could not be read ({err}).", ""]
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
    for step in (p.outbound, p.bookings, p.teardown_requests, p.nudges, p.teardowns, p.billing, p.proof,
                 p.data_requests, p.promises):
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
