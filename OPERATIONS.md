# Operations: the machine that looks for product-market fit

Nothing here needs a person at Hubricon during the week. The only thing the
founder still does by hand is show up to a call a prospect booked.

## The loop

```
Instantly campaign ──► reply ──► triage ──► TEARDOWN? ──► client + upload page
      ▲                                   └► interested ──► Calendly ──► booking ──► client + welcome
      │                                   └► question ──► answered from the fact sheet
   lead lists + SuperSearch                                     │
                                                                ▼
                                           uploads ──► models ──► Issue 001 in the desk ──► "it's ready" email
                                                                │
                                                                ▼
                                                 Stripe (paid) ──► renewed past the free month = PMF signal
```

Three components, each doing only what it is placed to do:

| Component | Where it runs | Sees | Does |
|---|---|---|---|
| `hubricon operator` | GitHub Actions, hourly (`.github/workflows/operator.yml`) | every secret | Instantly campaign, enrollment, reply sync + rule/Claude triage, sending replies, provisioning bookings and TEARDOWN requests, nudges, teardown runs, the daily digest |
| Cloud routine "Hubricon operator — inbox & triage" | claude.ai routines, every 2 h 8 am–6 pm Chicago | Gmail, Google Calendar, Supabase connectors | parses Calendly "New Event" emails into `bookings`; writes replies for anything still `pending_review` |
| `hubricon sweep` | GitHub Actions, Mondays | secrets | the existing weekly ingest / models / alerts pass for active clients |

The routine never sends email. The operator never reads the inbox. Both talk
through Supabase (`bookings`, `prospect_messages`, `funnel_events`,
`operator_state`).

## The one-time setup (five minutes, once)

GitHub → repo → Settings → Environments → **Production** → add:

| Secret | Why |
|---|---|
| `INSTANTLY_API_KEY` | Instantly → Settings → Integrations → API keys → v2 key with `all:all`. Outbound is OFF until this exists. Needs the Growth plan or above. |
| `POSTAL_ADDRESS` | A mailing address (PO box is fine). CAN-SPAM requires one in every cold email; the operator refuses to create the campaign without it. |
| `ANTHROPIC_API_KEY` | Optional. Lets the hourly run answer prospect questions itself instead of waiting up to 2 h for the routine. Same key as `.env`. |

The other five secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`RESEND_API_KEY`, `ALERT_FROM`, `FOUNDER_EMAIL`) are already there from the
sweep.

In Instantly itself: at least one mailbox on gethubricon.com connected with
warmup on. The operator only sends from mailboxes whose warmup is active and
sizes the daily limit to 20 per mailbox (cap 60). Lead lists whose name
contains "Hubricon" are enrolled automatically; SuperSearch is asked for 25
founders a day on top, best effort.

## What "PMF" means here, in numbers

`hubricon scoreboard` (or the daily digest) prints:

- contacted → replied → interested → bookings → onboarding → teardowns delivered
- paid → **renewed past the free month** → churned

The bar is **3 clients renewed past the free month at full price**. Below
that we are learning; above it, growth tactics are worth running. The
scoreboard excludes every internal address and the dry-run workspace.

## Reading the digest

Arrives at 8:17 am Chicago from the operator. Sections:

- **PMF scoreboard** — the numbers above.
- **Instantly campaign** — sent / replies / bounces as Instantly reports them.
- **Replies waiting for a written answer** — the routine clears these within
  two hours; if a name sits there for a day, the routine is not running
  (check https://claude.ai/code/routines).
- **Only you can do these** — booked calls with times; teardowns delivered
  (optionally record a Loom and attach it with `hubricon brief … --video`).
- **Warnings** — missing secrets, API errors, a client whose files failed to
  parse.

## Running it by hand

```
cd engine
uv run hubricon operator --dry-run          # read everything, change nothing
uv run hubricon operator --send             # one real pass
uv run hubricon operator --send --digest    # …and email the digest
uv run hubricon scoreboard
```

Actions → "Hourly operator" → Run workflow does the same in the cloud (tick
"dry run" to rehearse).

## Guardrails

- Cold email is 3 plain-text steps over 8 days, weekdays 8–5 Chicago,
  unsubscribe header on, opens and links untracked, stops on any reply,
  stops for the whole company on a reply. Every claim in it is on the site.
- Replies to prospects come from templates or from Claude constrained to the
  fact sheet in `engine/src/hubricon_engine/triage.py`. No numbers the engine
  did not compute, no discounts, no guarantees.
- `not interested`, `unsubscribe`, out-of-office and bounces get no reply and
  the lead is closed in Instantly.
- Internal addresses (hubricon.com, gethubricon.com, hubricon.internal, the
  founder's Gmail, "John Doe") are never prospects, never clients, never
  counted.
- Prospects who say "later" get `follow_up_at` 90 days out; nothing
  re-contacts them automatically yet.
