import { createClient } from "@supabase/supabase-js";

/**
 * The public teardown page.
 *
 *   GET  /t/<token>                  -> the rendered page (200), gone (404), expired (410)
 *   GET  /t/<token>?cta=1            -> records the click, 302 to the application gate
 *   POST /api/teardown?t=&e=<kind>   -> records a page_view / cta_click beacon, 204
 *
 * The HTML is rendered once by the engine and stored on the row, so this
 * function serves bytes and never models anything. That is deliberate: the
 * founder approves the exact page a prospect will see, and nothing between his
 * approval and their browser can change a number on it.
 *
 * A teardown is only visible once it has been approved. A draft is a page about
 * a stranger's business that nobody has read yet, and an unlisted URL is not a
 * permission — so an unapproved token answers 404, exactly like a wrong one.
 */

const APPLY_URL = process.env.TEARDOWN_CTA_URL || "https://hubricon.com/#apply";
const VISIBLE = new Set(["approved", "sent"]);
const EVENTS = new Set(["page_view", "cta_click", "video_watch"]);

function supabase() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

/** Tokens are the 32 url-safe characters of secrets.token_urlsafe(24). */
function cleanToken(raw) {
  const t = String(raw || "").trim();
  return /^[A-Za-z0-9_-]{16,64}$/.test(t) ? t : null;
}

const notFound = () => new Response("Not found", { status: 404 });

async function load(request) {
  const url = new URL(request.url);
  const token = cleanToken(url.searchParams.get("t"));
  if (!token) return { url, error: notFound() };
  const db = supabase();
  if (!db) {
    return { url, error: new Response("Server not configured", { status: 500 }) };
  }
  const { data, error } = await db
    .from("teardowns")
    .select("id, html, status, expires_at")
    .eq("token", token)
    .maybeSingle();
  if (error) return { url, error: new Response("Could not load this teardown", { status: 500 }) };
  if (!data || !VISIBLE.has(data.status)) return { url, error: notFound() };
  return { url, db, teardown: data };
}

async function logEvent(db, teardownId, kind, detail) {
  try {
    await db.from("teardown_events").insert({ teardown_id: teardownId, kind, detail });
  } catch {
    // An event we failed to write is worth less than the page we were serving.
  }
}

function expiredPage() {
  return new Response(
    `<!doctype html><html lang="en"><meta charset="utf-8">` +
      `<meta name="viewport" content="width=device-width,initial-scale=1">` +
      `<title>This teardown has expired</title>` +
      `<body style="font:16px/1.65 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;` +
      `background:hsl(222 28% 96%);color:hsl(228 26% 26%);padding:64px 24px;max-width:34em;margin:0 auto">` +
      `<h1 style="font:500 30px/1.2 Georgia,serif;color:hsl(228 44% 11%);margin:0 0 14px">` +
      `This teardown has expired</h1>` +
      `<p>Its numbers came off public pages that have moved since, so it is gone rather than ` +
      `quietly wrong. <a href="${APPLY_URL}" style="color:hsl(40 96% 33%)">Ask for a current one</a> ` +
      `and we will run it on your real figures instead.</p>`,
    { status: 410, headers: { "Content-Type": "text/html; charset=utf-8" } }
  );
}

export async function GET(request) {
  const { url, db, teardown, error } = await load(request);
  if (error) return error;

  const beacon = url.searchParams.get("e");
  if (EVENTS.has(beacon)) {
    await logEvent(db, teardown.id, beacon, { via: "img" });
    return new Response(null, { status: 204 });
  }

  if (new Date(teardown.expires_at) < new Date()) return expiredPage();

  if (url.searchParams.get("cta")) {
    await logEvent(db, teardown.id, "cta_click", {
      referer: request.headers.get("referer") || null,
    });
    return new Response(null, {
      status: 302,
      headers: { Location: APPLY_URL, "Cache-Control": "no-store" },
    });
  }

  await logEvent(db, teardown.id, "page_view", {
    ua: (request.headers.get("user-agent") || "").slice(0, 200),
  });
  return new Response(teardown.html, {
    status: 200,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      // Unlisted is not the same as secret: keep it out of every index and out
      // of any shared cache.
      "X-Robots-Tag": "noindex, nofollow",
      "Cache-Control": "private, max-age=0, must-revalidate",
    },
  });
}

/** navigator.sendBeacon posts with no body; the event is in the query string. */
export async function POST(request) {
  const { url, db, teardown, error } = await load(request);
  if (error) return error;
  const kind = url.searchParams.get("e");
  if (EVENTS.has(kind)) {
    await logEvent(db, teardown.id, kind, {
      referer: request.headers.get("referer") || null,
      ua: (request.headers.get("user-agent") || "").slice(0, 200),
    });
  }
  return new Response(null, { status: 204 });
}
