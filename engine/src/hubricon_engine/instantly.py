"""Instantly API v2: the cold-outreach channel.

Thin client over urllib — no SDK, no retries beyond one, every error surfaced
as InstantlyError with the response body so the operator digest can say
exactly why a step failed. Env-gated on INSTANTLY_API_KEY: without it,
`configured()` is False and the operator skips outbound with a loud line.

Endpoints (https://developer.instantly.ai, API v2, Growth plan and above):
  GET  /accounts                       linked mailboxes + warmup state
  GET  /campaigns, POST /campaigns     find / create the campaign
  POST /campaigns/{id}/activate
  GET  /campaigns/analytics
  GET  /lead-lists, POST /leads/list   lead lists the founder built in Instantly
  POST /leads                          enroll a lead into the campaign
  DELETE /leads/{id}                   drop a lead (harvest prune)
  PATCH /leads/{id}                    interest status
  GET  /emails                         unibox (replies), 20 req/min
  POST /emails/{id}/reply              reply from the same mailbox
  POST /supersearch-enrichment/enrich  Instantly's own lead database (best effort)
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.instantly.ai/api/v2"

# Account.status / warmup_status enums from the OpenAPI spec.
ACCOUNT_ACTIVE = 1
WARMUP_ACTIVE = 1
# Campaign.status
CAMPAIGN_DRAFT, CAMPAIGN_ACTIVE, CAMPAIGN_PAUSED, CAMPAIGN_COMPLETED = 0, 1, 2, 3
# Email.ue_type
UE_SENT_FROM_CAMPAIGN, UE_RECEIVED, UE_SENT, UE_SCHEDULED = 1, 2, 3, 4


class InstantlyError(RuntimeError):
    def __init__(self, status: int, path: str, body: str):
        super().__init__(f"Instantly {status} on {path}: {body[:300]}")
        self.status = status
        self.path = path
        self.body = body


def configured() -> bool:
    return bool(os.environ.get("INSTANTLY_API_KEY"))


class Instantly:
    def __init__(self, api_key: str | None = None, timeout: int = 30):
        self.key = api_key or os.environ.get("INSTANTLY_API_KEY")
        if not self.key:
            raise InstantlyError(0, "", "INSTANTLY_API_KEY is not set")
        self.timeout = timeout

    # -- transport ---------------------------------------------------------
    def _call(self, method: str, path: str, body: dict | None = None, params: dict | None = None):
        url = BASE + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"authorization": f"Bearer {self.key}", "content-type": "application/json",
                     "accept": "application/json",
                     # Cloudflare in front of api.instantly.ai answers "error 1010"
                     # to Python's default user agent; a named client passes.
                     "user-agent": "Hubricon-operator/1.0 (+https://www.hubricon.com)"},
        )
        for attempt in (1, 2):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as res:
                    raw = res.read().decode()
                    return json.loads(raw) if raw.strip() else {}
            except urllib.error.HTTPError as err:
                text = err.read().decode(errors="replace")
                if err.code == 429 and attempt == 1:
                    time.sleep(4)
                    continue
                raise InstantlyError(err.code, path, text) from None
            except (urllib.error.URLError, TimeoutError) as err:
                if attempt == 1:
                    time.sleep(2)
                    continue
                raise InstantlyError(0, path, str(err)) from None

    def _page(self, method: str, path: str, body: dict | None = None, params: dict | None = None,
              limit: int = 100, max_items: int = 5000) -> list[dict]:
        """Cursor pagination: `starting_after` in, `next_starting_after` out."""
        items: list[dict] = []
        cursor = None
        while True:
            if method == "GET":
                page = self._call("GET", path, params={**(params or {}), "limit": limit, "starting_after": cursor})
            else:
                page = self._call("POST", path, body={**(body or {}), "limit": limit,
                                                      **({"starting_after": cursor} if cursor else {})})
            batch = page.get("items", page if isinstance(page, list) else [])
            items.extend(batch)
            cursor = page.get("next_starting_after") if isinstance(page, dict) else None
            if not cursor or not batch or len(items) >= max_items:
                return items

    # -- accounts ----------------------------------------------------------
    def accounts(self) -> list[dict]:
        return self._page("GET", "/accounts")

    def ready_senders(self) -> list[dict]:
        """Mailboxes that are connected and past warmup, the only ones we send from."""
        return [a for a in self.accounts()
                if a.get("status") == ACCOUNT_ACTIVE and a.get("warmup_status") == WARMUP_ACTIVE]

    # -- campaigns ---------------------------------------------------------
    def campaigns(self) -> list[dict]:
        return self._page("GET", "/campaigns")

    def find_campaign(self, name: str) -> dict | None:
        for c in self.campaigns():
            if c.get("name") == name:
                return c
        return None

    def create_campaign(self, spec: dict) -> dict:
        return self._call("POST", "/campaigns", body=spec)

    def activate_campaign(self, campaign_id: str) -> dict:
        return self._call("POST", f"/campaigns/{campaign_id}/activate", body={})

    def update_campaign(self, campaign_id: str, fields: dict) -> dict:
        """PATCH /campaigns/{id}: e.g. {"sequences": [...]} swaps the copy in place,
        so threads already sent keep their history."""
        return self._call("PATCH", f"/campaigns/{campaign_id}", body=fields)

    def campaign_analytics(self, campaign_id: str) -> dict:
        out = self._call("GET", "/campaigns/analytics", params={"campaign_id": campaign_id})
        if isinstance(out, list):
            return out[0] if out else {}
        return out

    # -- leads -------------------------------------------------------------
    def lead_lists(self) -> list[dict]:
        return self._page("GET", "/lead-lists")

    def leads_in_list(self, list_id: str) -> list[dict]:
        return self._page("POST", "/leads/list", body={"list_id": list_id})

    def leads_in_campaign(self, campaign_id: str) -> list[dict]:
        return self._page("POST", "/leads/list", body={"campaign": campaign_id})

    def create_lead(self, campaign_id: str, email: str, first_name: str | None = None,
                    last_name: str | None = None, company_name: str | None = None,
                    website: str | None = None, custom: dict | None = None) -> dict:
        body = {
            "campaign": campaign_id,
            "email": email,
            "skip_if_in_workspace": True,
            "skip_if_in_campaign": True,
            "verify_leads_on_import": True,
        }
        for k, v in (("first_name", first_name), ("last_name", last_name),
                     ("company_name", company_name), ("website", website)):
            if v:
                body[k] = v
        if custom:
            body["custom_variables"] = custom
        return self._call("POST", "/leads", body=body)

    def set_interest(self, lead_id: str, lt_interest_status: int) -> dict:
        # 1 interested · 2 meeting booked · 3 meeting completed · 4 closed ·
        # 0 out of office · -1 not interested · -2 wrong person · -3 lost
        return self._call("PATCH", f"/leads/{lead_id}", body={"lt_interest_status": lt_interest_status})

    def leads_by_email(self, email: str) -> list[dict]:
        """Every lead object carrying this address, across lists and campaigns
        (a list upload and a campaign enrolment are two objects)."""
        page = self._call("POST", "/leads/list", body={"search": email, "limit": 20})
        items = page.get("items", page if isinstance(page, list) else []) if page else []
        return [l for l in items if (l.get("email") or "").lower() == email.lower()]

    def delete_lead(self, lead_id: str) -> dict:
        """DELETE /leads/{id}: drop a lead from its list or campaign before it is
        emailed (the harvest prunes sellers that turned out to be giants)."""
        return self._call("DELETE", f"/leads/{lead_id}")

    def create_lead_list(self, name: str) -> dict:
        return self._call("POST", "/lead-lists", body={"name": name})

    def add_leads(self, list_id: str | None = None, campaign_id: str | None = None,
                  leads: list[dict] | None = None) -> dict:
        """POST /leads/add: up to 1000 leads into a list *or* a campaign. Instantly
        validates each address on import and skips ones already in the workspace."""
        if bool(list_id) == bool(campaign_id):
            raise InstantlyError(0, "/leads/add", "give exactly one of list_id / campaign_id")
        body = {
            "leads": leads or [],
            "verify_leads_on_import": True,
            "skip_if_in_workspace": True,
            "skip_if_in_campaign": True,
            "skip_if_in_list": True,
        }
        if list_id:
            body["list_id"] = list_id
        else:
            body["campaign_id"] = campaign_id
        return self._call("POST", "/leads/add", body=body)

    def supersearch_count(self, filters: dict) -> dict:
        return self._call("POST", "/supersearch-enrichment/count-leads-from-supersearch",
                          body={"search_filters": filters, "skip_owned_leads": True,
                                "show_one_lead_per_company": True})

    def supersearch_enrich(self, list_id: str, filters: dict, limit: int, search_name: str) -> dict:
        """Instantly's lead database → a lead list (the API targets lists, not
        campaigns; the operator enrolls the list into the campaign on its next
        pass). Runs as a background job on Instantly's side; the response
        carries background_job_id. Schema from api.instantly.ai/openapi/api_v2.json."""
        body = {
            "search_filters": filters,
            "limit": limit,
            "resource_id": list_id,
            "search_name": search_name,
            "work_email_enrichment": True,
            "skip_rows_without_email": True,
        }
        return self._call("POST", "/supersearch-enrichment/enrich-leads-from-supersearch", body=body)

    # -- unibox ------------------------------------------------------------
    def received_emails(self, campaign_id: str, max_items: int = 500) -> list[dict]:
        """Inbound replies on the campaign (ue_type 2), filtered client-side so
        an unknown query flag can't silently return nothing."""
        rows = self._page("GET", "/emails", params={"campaign_id": campaign_id, "email_type": "received"},
                          limit=100, max_items=max_items)
        return [r for r in rows if r.get("ue_type") == UE_RECEIVED]

    def reply(self, email_id: str, eaccount: str, subject: str, text: str, html: str | None = None) -> dict:
        body = {
            "eaccount": eaccount,
            "reply_to_uuid": email_id,
            "subject": subject,
            "body": {"text": text, "html": html or "<br/>".join(text.split("\n"))},
        }
        return self._call("POST", "/emails/reply", body=body)
