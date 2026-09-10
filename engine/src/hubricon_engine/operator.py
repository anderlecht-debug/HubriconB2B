"""The operator: one hourly pass that runs the funnel end to end.

  1. Outbound  — campaign up, leads in, replies triaged and answered (Instantly).
  2. Bookings  — Calendly bookings the cloud routine parsed → client + welcome email.
  3. TEARDOWN  — prospects who replied with the keyword → client + upload page.
  4. Nudges    — clients who haven't uploaded after 3 / 7 days, once each.
  5. Teardown  — new uploads parsed; first successful run → Issue 001 in the
                 desk, report file in storage, "it's ready" email.
  6. Billing   — the day-30 gate; the only code that starts a subscription.
  7. Proof     — every verified dollar becomes a result row; consented rows
                 go public and the cold copy picks up the record by itself.
  8. Digest    — the PMF scoreboard, the loop past paid, speed to value, and
                 anything only a human can do, emailed to the founder daily.

Everything is idempotent, so an hourly run that finds nothing does nothing.
"""

import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

from . import channels
from . import db as dbmod
from . import instantly, onboarding, outbound, proof, referral, speed
from .briefing import build_memo, period_deltas
from .notify import email_configured, send_email

PORTAL_URL = os.environ.get("INTAKE_BASE_URL", "https://www.hubricon.com") + "/portal"  # mirrors cli.PORTAL_URL
NUDGE_AFTER_DAYS = 3
FILES_AFTER_DAYS = 7
DOWNSELL_AFTER_DAYS = 14     # the smaller door, once, to an Amazon seller whose exports never came


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
            platform = onboarding.platform_from_answers(b.get("answers"))
            client, link, created = onboarding.provision(self.db, email, b.get("invitee_name"), company, platform)
            self._attribute_booking(client, b, email)
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
            # A prospect the harvest found on a Shopify store must not be sent
            # Seller Central instructions: the harvest row knows the platform,
            # and so does the 60-second Teardown's capture (tool_runs) for a
            # merchant who arrived through /teardown rather than the cold lane.
            harvested = (self.db.table("harvest_sellers").select("platform")
                         .eq("email", email).limit(1).execute().data)
            platform = (harvested[0].get("platform") if harvested else None)
            if not platform:
                runs = (self.db.table("tool_runs").select("platform").eq("email", email)
                        .order("created_at", desc=True).limit(1).execute().data)
                platform = runs[0].get("platform") if runs else None
            platform = platform or "amazon"
            client, link, created = onboarding.provision(self.db, email, name, p.get("company_name"), platform)
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
            amazon = (c.get("platform") or "amazon") in ("amazon", "both")
            if (age >= DOWNSELL_AFTER_DAYS and "downsell" not in touches and amazon
                    and (c.get("plan") or "retainer") == "retainer"):
                self._reonboard(c, "downsell")
            elif age >= FILES_AFTER_DAYS and "files" not in touches:
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
        ok = onboarding.send(kind, client["contact_email"], client.get("contact_name"), link, PORTAL_URL,
                             platform=client.get("platform") or "amazon")
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
            # The clock the 24-hour promise runs from: the first pass that
            # found typed data on file, set once and never moved.
            if not self.dry and speed.set_once(self.db, c, "exports_landed_at"):
                outbound.log_event(self.db, "exports_landed", client_id=c["id"])
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
        # welcome.html: the 90-day plan is drafted from the Teardown within 24h
        # and presented on the kickoff call. It stays a draft until then.
        cli.draft_plan_for_run(self.db, c, run_id)
        margins = self.db.table("margin_results").select("*").eq("run_id", run_id).execute().data
        elasticity = self.db.table("elasticity_results").select("*").eq("run_id", run_id).execute().data
        first_name = (c.get("contact_name") or "").split(" ")[0]
        company = c["company_name"] or c["contact_email"]
        deltas = period_deltas(margins)
        memo = build_memo(company, first_name, deltas, [], [], elasticity, 0.0, 0, issue_number=1,
                          channel=channels.client_channel(c) or "amazon")
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

        video_path = None
        with tempfile.TemporaryDirectory() as tmp:
            path = generate(self.db, c, run_id=run_id, out_dir=tmp)
            report_path = f"reports/{c['id']}/issue-001.html"
            self.db.storage.from_(storage.BUCKET).upload(
                report_path, path.read_bytes(), {"content-type": "text/html", "upsert": "true"})

            # index.html, welcome.html, terms.html §2 and the portal all promise
            # a recorded walkthrough with the Teardown. This line used to be
            # `"video_id": None` and a note asking the founder to record a Loom.
            from pathlib import Path as _Path
            from . import video as videomod
            from .briefing import build_beats
            beats = build_beats(company, first_name, deltas, [], [], elasticity, 0.0, 0)
            made = videomod.render(company, 1, beats, _Path(tmp) / "issue-001.mp4")
            if made:
                video_path = f"reports/{c['id']}/issue-001.mp4"
                self.db.storage.from_(storage.BUCKET).upload(
                    video_path, made.read_bytes(), {"content-type": "video/mp4", "upsert": "true"})

        self.db.table("briefings").insert({
            "client_id": c["id"], "run_id": run_id, "video_id": None, "video_path": video_path,
            "memo": memo, "issue_number": 1,
            "report_path": report_path, "title": "Profit Teardown",
            "headline": "Issue No. 001 — your Profit Teardown",
        }).execute()
        speed.set_once(self.db, c, "first_issue_at")
        sent = self._touch(c, "teardown_ready", PORTAL_URL, force=True)
        outbound.log_event(self.db, "teardown_delivered", client_id=c["id"],
                           payload={"run_id": run_id, "emailed": sent, "video": bool(video_path)})
        self.db.table("prospects").update({"status": "client", "last_event_at": _iso()}).eq("email", c["contact_email"]).execute()
        self.say(f"Published Issue 001 for {company}"
                 + (" with video" if video_path else " (no video — see the warning)")
                 + f"; client {'emailed' if sent else 'NOT emailed'}.")
        if not video_path:
            # The copy promises a recorded walkthrough. If the pipeline could
            # not make one, that is a promise outstanding, not a nice-to-have.
            self.warnings.append(
                f"Issue 001 for {company} shipped WITHOUT the recorded walkthrough the site promises. "
                f"Record one now: `hubricon brief {c['contact_email']} --video <url>`.")

    # -- 6. the day-30 guarantee ---------------------------------------------
    def billing(self) -> None:
        """At day 30, compare the ledger to the fee and act on the answer.

        terms.html §3 promises no invoice unless we found more than we cost.
        This is the only code that starts billing, so the promise cannot be
        broken by forgetting — below the bar there is no subscription, and
        therefore no invoice to write off."""
        from . import billing, cli, value

        price_id = os.environ.get("STRIPE_PRICE_ID")
        clients = self.db.table("clients").select("*").in_("status", ["pending", "active"]).execute().data
        for c in clients:
            if onboarding.is_internal(c["contact_email"], c.get("contact_name")):
                continue
            # The smaller door: no retainer, a share of what Amazon paid back,
            # invoiced at month end. Never enters the day-30 machinery.
            if (c.get("plan") or "retainer") == "recovery":
                self._recovery_billing(c, cli, billing, value)
                continue
            # Already on the retainer: every new invoice meets the same bar.
            if c.get("stripe_subscription_id"):
                self._rolling_gate(c, cli, billing, value)
                continue
            due, why = billing.due_for_decision(c)
            if not due:
                continue

            directives = self.db.table("directives").select("*").eq("client_id", c["id"]).execute().data
            ledger = value.compute(c, directives, cli._fetch_claims(self.db, c["id"]),
                                   cli._fetch_invoices(self.db, c["id"]))
            v = billing.verdict(ledger, c)
            company = c["company_name"] or c["contact_email"]

            if self.dry:
                self.say(f"[dry] {company}: {why}; ledger ${v['total']:,.0f} vs ${v['fee']:,.0f} — "
                         f"{'would start billing' if v['clears'] else 'would NOT invoice'}")
                continue

            if not v["clears"]:
                # This pass runs hourly and the client stays "due" until they
                # clear, so the ref_id is the engagement, not the day — one
                # letter about the guarantee, not one a day. The work carries
                # on and later passes re-check, silently, until it clears.
                first_time = c.get("billing_decision") != "short"
                self.db.table("clients").update({
                    "billing_decided_at": _iso(), "billing_decision": "short",
                }).eq("id", c["id"]).execute()
                amazon = (c.get("platform") or "amazon") in ("amazon", "both")
                cli._send_client_email(self.db, c, "guarantee_short",
                                       str(c.get("retainer_started_at") or c["id"]),
                                       "Your free month, and what we found",
                                       billing.short_email_blocks(v, PORTAL_URL, recovery_door=amazon,
                                                                  share=c.get("recovery_share")), self.send)
                if first_time:
                    self.human.append(
                        f"{company} finished the free month at ${v['total']:,.0f} against a "
                        f"${v['fee']:,.0f} fee. No invoice was raised — that is the guarantee. "
                        f"Worth a call.")
                continue

            if not (price_id and billing.stripe_configured()):
                self.warnings.append(
                    f"{company} cleared the guarantee ({v['multiple']:.1f}x) but billing did not start: "
                    f"set STRIPE_SECRET_KEY and STRIPE_PRICE_ID. Nothing is lost — the next pass bills "
                    f"them once the secrets exist.")
                continue
            try:
                sub = billing.start_billing(c, price_id)
            except Exception as err:
                self.warnings.append(f"{company} cleared the guarantee but Stripe refused: {err}")
                continue
            self.db.table("clients").update({
                "stripe_subscription_id": sub["id"],
                "stripe_customer_id": sub.get("customer") or c.get("stripe_customer_id"),
                "status": "active", "billing_decided_at": _iso(), "billing_decision": "cleared",
            }).eq("id", c["id"]).execute()
            cli._send_client_email(self.db, c, "guarantee_cleared", sub["id"],
                                   "Your free month, and your first invoice",
                                   billing.cleared_email_blocks(v, PORTAL_URL), self.send)
            # The brand that sent them, if one did, earns its month now — not
            # at the booking, not at the yes: at the gate, when there is revenue.
            self._credit_referrer(c)
            # The stated price of the free month, asked for once and recorded.
            for kind in ("testimonial", "anonymised_results"):
                try:
                    self.db.table("consents").upsert(
                        {"client_id": c["id"], "kind": kind}, on_conflict="client_id,kind").execute()
                except Exception:
                    pass
            self.say(f"{company} cleared the guarantee at {v['multiple']:.1f}x — billing started.")

    def _rolling_gate(self, c: dict, cli, billing, value) -> None:
        """terms §3: our invoices never run ahead of the ledger.

        Every invoice Stripe has raised and nobody has judged is measured by
        the day-30 bar — measured plus identified since the retainer began
        against everything billed through it. Covered is written on the row;
        not covered is voided (or credited if ACH already settled) and the
        client is told in one letter. Decided exactly once per invoice."""
        company = c["company_name"] or c["contact_email"]
        invoices = cli._fetch_invoices(self.db, c["id"])
        pending = billing.unjudged_invoices(invoices, c)
        if not pending:
            return
        directives = self.db.table("directives").select("*").eq("client_id", c["id"]).execute().data
        ledger = value.compute(c, directives, cli._fetch_claims(self.db, c["id"]), invoices)
        for inv in pending:
            v = billing.rolling_verdict(ledger, invoices, inv, c)
            label = f"invoice {inv.get('number') or str(inv.get('stripe_invoice_id'))[:12]}"
            if self.dry:
                self.say(f"[dry] {company}: {label} — ledger ${v['total']:,.0f} vs ${v['fees_billed']:,.0f} billed — "
                         f"{'covered' if v['covered'] else 'would be WAIVED'}")
                continue
            if v["covered"]:
                self.db.table("invoices").update({
                    "gate_decision": "covered", "gate_decided_at": _iso(),
                    "gate_value": round(v["total"], 2), "gate_fees": round(v["fees_billed"], 2),
                }).eq("id", inv["id"]).execute()
                self.say(f"{company}: {label} covered — ledger ${v['total']:,.0f} against ${v['fees_billed']:,.0f} billed.")
                continue
            if not billing.stripe_configured():
                self.warnings.append(f"{company}: {label} is NOT covered by the ledger (${v['total']:,.0f} vs "
                                     f"${v['fees_billed']:,.0f}) and cannot be waived: STRIPE_SECRET_KEY missing.")
                continue
            try:
                how = billing.waive_invoice(inv, c)
            except Exception as err:
                self.warnings.append(f"{company}: {label} should be waived but Stripe refused: {err}")
                continue
            self.db.table("invoices").update({
                "gate_decision": "waived", "gate_decided_at": _iso(), "gate_note": how,
                "gate_value": round(v["total"], 2), "gate_fees": round(v["fees_billed"], 2),
                **({"status": "void", "voided_at": _iso()} if how == "voided" else {}),
            }).eq("id", inv["id"]).execute()
            cli._send_client_email(self.db, c, "month_waived", str(inv.get("stripe_invoice_id")),
                                   "This month is on us",
                                   billing.waived_email_blocks(v, how, PORTAL_URL), self.send)
            self.human.append(f"{company}: {label} {how} — the ledger (${v['total']:,.0f}) had fallen behind "
                              f"the bills (${v['fees_billed']:,.0f}). The work has to catch up; worth a call.")
            self.say(f"{company}: {label} {how} — the ledger had not covered it.")

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
        """Legal clocks, surfaced before they run out.

        privacy.html gives a number of days for each of these. Nothing counted
        them, so the only alarm was the requester following up."""
        try:
            rows = (self.db.table("data_requests").select("*").is_("closed_at", "null")
                    .order("due_at").execute().data)
        except Exception:
            return      # table not migrated yet
        now = _now()
        for r in rows:
            left = (datetime.fromisoformat(str(r["due_at"])) - now).days
            who = r.get("requester_email") or "—"
            if left < 0:
                self.warnings.append(f"OVERDUE by {abs(left)}d: {r['kind']} request from {who} "
                                     f"({r['id'][:8]}). The privacy policy gives a deadline; this is past it.")
            elif left <= 2:
                self.human.append(f"{r['kind']} request from {who} is due in {left}d ({r['id'][:8]}).")

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
