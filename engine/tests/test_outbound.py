from hubricon_engine import outbound
from hubricon_engine.outbound import CAMPAIGN_NAME, campaign_spec


def test_campaign_spec_is_one_plain_text_email_with_compliance_footer():
    spec = campaign_spec(["hagen@gethubricon.com", "h@gethubricon.com"], "123 Main St, Dallas, TX 75201")
    assert spec["name"] == CAMPAIGN_NAME
    steps = spec["sequences"][0]["steps"]
    assert len(steps) == 1 and steps[0]["type"] == "email" and steps[0]["delay"] == 0  # no follow-ups, ever
    body = steps[0]["variants"][0]["body"]
    assert "123 Main St" in body and "stop emailing" in body
    assert "{{firstName}}" in body and "{{companyName}}" in body
    assert "TEARDOWN" in body
    assert "<br/>" in body and "\n" not in body  # Instantly wants <br/> line breaks
    assert steps[0]["variants"][0]["subject"]
    # the offer, the honest reason it's free, the price of the seat, the risk reversal — all on the site
    for claim in ("first month", "free", "testimonial", "anonymized", "walk away owing nothing", "24 hours",
                  "three-minute brief", "No card", "new"):
        assert claim.lower() in body.lower(), claim
    prose = body.replace(outbound.CALENDLY_URL, "")  # the booking slug is legacy, the prose is not
    assert "audit" not in prose.lower()  # banned client-facing word
    assert "seats" not in prose.lower() and "spots" not in prose.lower()  # no scarcity claims
    assert spec["text_only"] and spec["insert_unsubscribe_header"] and spec["stop_on_reply"]
    assert not spec["open_tracking"] and not spec["link_tracking"]
    assert spec["email_list"] == ["hagen@gethubricon.com", "h@gethubricon.com"]


def test_daily_limit_scales_with_mailboxes_but_is_capped():
    assert campaign_spec(["a@x.com"], "addr")["daily_limit"] == outbound.PER_MAILBOX_DAILY
    assert campaign_spec(["a@x.com"] * 10, "addr")["daily_limit"] == outbound.CAMPAIGN_DAILY_CAP
    assert campaign_spec([], "addr")["daily_limit"] == outbound.PER_MAILBOX_DAILY


def test_schedule_is_us_business_hours_on_weekdays():
    sched = campaign_spec(["a@x.com"], "addr")["campaign_schedule"]["schedules"][0]
    assert sched["timezone"] == "America/Chicago"
    assert set(sched["days"]) == {"1", "2", "3", "4", "5"}
    assert sched["timing"] == {"from": "08:00", "to": "17:00"}


def test_supersearch_filters_use_instantly_vocabulary():
    # enums copied from api.instantly.ai/openapi/api_v2.json
    revenue_enum = {"$0 - 1M", "$1 - 10M", "$10 - 50M", "$50 - 100M", "$100 - 250M", "$250 - 500M", "$500M - 1B", "> $1B"}
    employee_enum = {"0 - 25", "25 - 100", "100 - 250", "250 - 1000", "1K - 10K", "10K - 50K", "50K - 100K", "> 100K"}
    f = outbound.SUPERSEARCH_FILTERS
    assert set(f["revenue"]) <= revenue_enum and "$0 - 1M" not in f["revenue"]
    assert set(f["employeeCount"]) <= employee_enum
    assert isinstance(f["keyword_filter"]["include"], str) and f["keyword_filter"]["include_mode"] in ("ANY", "ALL")
    # the service providers who *talk about* FBA are excluded by keyword and by industry enum
    industry_enum = {"Agriculture & Mining", "Business Services", "Computers & Electronics", "Consumer Services",
                     "Education", "Energy & Utilities", "Financial Services", "Government",
                     "Healthcare, Pharmaceuticals, & Biotech", "Manufacturing", "Media & Entertainment", "Non-Profit",
                     "Other", "Real Estate & Construction", "Retail", "Software & Internet", "Telecommunications",
                     "Transportation & Storage", "Travel, Recreation, and Leisure", "Wholesale & Distribution"}
    assert isinstance(f["keyword_filter"]["exclude"], str) and "agency" in f["keyword_filter"]["exclude"]
    assert set(f["industry"]["exclude"]) <= industry_enum
    assert not ({"Retail", "Manufacturing", "Consumer Services"} & set(f["industry"]["exclude"]))  # brands live here
    assert f["title"]["includeMode"] in ("EXACT", "CONTAINS") and "Founder" in f["title"]["include"]
    assert f["locations"] == {"include": [{"country": "United States"}]}
    assert f["location_mode"] in ("contact", "company")
    assert outbound.LIST_MATCH in outbound.SUPERSEARCH_LIST.lower()  # the auto list enrolls itself


def test_every_step_word_count_stays_short():
    spec = campaign_spec(["a@x.com"], "addr")
    for s in spec["sequences"][0]["steps"]:
        words = s["variants"][0]["body"].replace("<br/>", " ").split()
        assert len(words) <= 130, len(words)


# -- the live campaign follows the copy in this file -------------------------------

class _Result:
    def __init__(self, data):
        self.data = data


class _Table:
    def __init__(self, store, name):
        self.rows = store.setdefault(name, [])
        self._key = None

    def select(self, *_):
        return self

    def eq(self, k, v):
        self._key = (k, v)
        return self

    def execute(self):
        if self._key is None:  # after insert/upsert: nothing to read back
            return _Result([])
        k, v = self._key
        return _Result([dict(r) for r in self.rows if r.get(k) == v])

    def upsert(self, row, on_conflict="key"):
        for i, r in enumerate(self.rows):
            if r.get(on_conflict) == row.get(on_conflict):
                self.rows[i] = {**r, **row}
                break
        else:
            self.rows.append(dict(row))
        return self

    def insert(self, row):
        self.rows.append(dict(row))
        return self


class _DB:
    def __init__(self):
        self.store = {}

    def table(self, name):
        return _Table(self.store, name)


class _Api:
    def __init__(self):
        self.updated, self.activated = [], []

    def campaigns(self):
        return [{"id": "C1", "name": CAMPAIGN_NAME, "status": outbound.CAMPAIGN_ACTIVE}]

    def find_campaign(self, name):
        return self.campaigns()[0]

    def ready_senders(self):
        return [{"email": "hagen@gethubricon.com"}]

    def update_campaign(self, cid, fields):
        self.updated.append((cid, fields))
        return {}

    def activate_campaign(self, cid):
        self.activated.append(cid)

    def create_campaign(self, spec):
        raise AssertionError("the campaign already exists")


def test_existing_campaign_gets_the_new_copy_once():
    db, api = _DB(), _Api()
    cid, notes = outbound.ensure_campaign(db, api, "123 Main St", dry=False)
    assert cid == "C1" and len(api.updated) == 1
    _, fields = api.updated[0]
    assert list(fields) == ["sequences"] and len(fields["sequences"][0]["steps"]) == 1
    assert any("no follow-ups" in n for n in notes)
    assert outbound.get_state(db, "instantly.campaign")["copy_version"] == outbound.COPY_VERSION
    assert db.store["funnel_events"][0]["kind"] == "campaign_copy_updated"
    # second pass: version matches, nothing is sent to Instantly
    outbound.ensure_campaign(db, api, "123 Main St", dry=False)
    assert len(api.updated) == 1 and not api.activated


def test_copy_update_respects_dry_run_and_needs_the_postal_footer():
    db, api = _DB(), _Api()
    _, notes = outbound.ensure_campaign(db, api, "123 Main St", dry=True)
    assert not api.updated and any(n.startswith("[dry] would update the campaign copy") for n in notes)
    _, notes = outbound.ensure_campaign(db, api, None, dry=False)
    assert not api.updated and any("POSTAL_ADDRESS" in n for n in notes)


def test_instantly_call_sets_json_content_type_only_with_a_body(monkeypatch):
    import json as _json
    import urllib.request

    from hubricon_engine import instantly as im

    seen = []

    class _Res:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def fake_urlopen(req, timeout=None):
        seen.append((req.get_method(), dict(req.header_items()), req.data))
        return _Res()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    api = im.Instantly(api_key="k")
    api.delete_lead("L1")
    api.create_lead_list("x")
    delete, post = seen
    assert delete[0] == "DELETE" and delete[2] is None and not any(k.lower() == "content-type" for k in delete[1])
    assert post[0] == "POST" and _json.loads(post[2]) == {"name": "x"} and any(k.lower() == "content-type" for k in post[1])
