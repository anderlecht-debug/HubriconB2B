/**
 * Branded transactional email for the onboarding scripts.
 *
 * Sends through Resend's REST API from the same identity the portal's
 * sign-in link uses (Hagen Simmons <hagen.simmons@hubricon.com>), so every
 * email a client receives looks like it came from the same desk. The HTML
 * mirrors supabase/templates/magic-link.html on purpose.
 *
 * Content is a small block list so one definition renders both the HTML
 * the client sees and the plain text we print to the console (and attach
 * as the text/plain MIME part):
 *
 *   { p: "paragraph" }
 *   { path: "Settings → User Permissions → …" }      monospace line
 *   { button: "label", url: "https://…" }             button + visible URL
 *   { ol: ["first", "second"] }                        numbered list
 */

export const DEFAULT_FROM = "Hagen Simmons <hagen.simmons@hubricon.com>";

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const P = 'style="font-size:16px;margin:0 0 20px"';
const SMALL = 'style="font-size:14px;color:#555;margin:0 0 20px"';

function htmlBlock(b) {
  if (b.p) return `  <p ${P}>${esc(b.p)}</p>`;
  if (b.path) {
    return `  <p style="font-family:Menlo,Consolas,monospace;font-size:14px;background:#f2f2f2;padding:10px 14px;margin:0 0 20px">${esc(b.path)}</p>`;
  }
  if (b.button) {
    return [
      `  <p style="margin:0 0 10px">`,
      `    <a href="${esc(b.url)}"`,
      `       style="display:inline-block;background:#1a1a1a;color:#ffffff;text-decoration:none;padding:12px 24px;font-size:15px">`,
      `      ${esc(b.button)}`,
      `    </a>`,
      `  </p>`,
      `  <p ${SMALL}><a href="${esc(b.url)}" style="color:#555;word-break:break-all">${esc(b.url)}</a></p>`,
    ].join("\n");
  }
  if (b.ol) {
    const items = b.ol.map((i) => `    <li style="margin:0 0 10px">${esc(i)}</li>`).join("\n");
    return `  <ol style="font-size:15px;padding-left:22px;margin:0 0 20px">\n${items}\n  </ol>`;
  }
  throw new Error(`Unknown email block: ${JSON.stringify(b)}`);
}

export function renderHtml({ greeting, blocks }) {
  return [
    `<div style="max-width:520px;margin:0 auto;padding:32px 24px;font-family:Georgia,'Times New Roman',serif;color:#1a1a1a;line-height:1.6">`,
    `  <p style="font-size:15px;letter-spacing:0.08em;text-transform:uppercase;color:#8a8a8a;margin:0 0 28px">Hubricon</p>`,
    greeting ? `  <p ${P}>${esc(greeting)}</p>` : "",
    ...blocks.map(htmlBlock),
    `  <p ${P}>Best,</p>`,
    `  <p style="font-size:14px;margin:0">Hagen Simmons<br><span style="color:#8a8a8a">Hubricon</span></p>`,
    `</div>`,
  ]
    .filter(Boolean)
    .join("\n");
}

function textBlock(b) {
  if (b.p) return b.p;
  if (b.path) return `  ${b.path}`;
  if (b.button) return `  ${b.url}`;
  if (b.ol) return b.ol.map((i, n) => `${n + 1}. ${i}`).join("\n");
  throw new Error(`Unknown email block: ${JSON.stringify(b)}`);
}

export function renderText({ greeting, blocks }) {
  return [greeting, ...blocks.map(textBlock), "Best,\nHagen — Hubricon"].filter(Boolean).join("\n\n");
}

export function emailConfigured() {
  return Boolean(process.env.RESEND_API_KEY);
}

/** Sends one email through Resend; resolves to the Resend message id. */
export async function sendEmail({ to, subject, html, text }) {
  const key = process.env.RESEND_API_KEY;
  if (!key) throw new Error("RESEND_API_KEY is not set");
  const from = process.env.EMAIL_FROM ?? DEFAULT_FROM;
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({ from, to: [to], reply_to: process.env.EMAIL_REPLY_TO ?? from, subject, html, text }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`Resend ${res.status}: ${body.message ?? JSON.stringify(body)}`);
  return body.id;
}
