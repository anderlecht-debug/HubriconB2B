/**
 * Branded transactional email for the onboarding scripts.
 *
 * Sends through Resend's REST API from the same identity the portal's
 * sign-in link uses (Hagen Simmons <hagen.simmons@hubricon.com>), so every
 * email a client receives comes from the same person, in the same look as
 * supabase/templates/magic-link.html (lib/tool_email.js holds it).
 *
 * Content is a small block list so one definition renders both the HTML
 * the client sees and the plain text we print to the console (and attach
 * as the text/plain MIME part):
 *
 *   { p: "paragraph" }
 *   { path: "Settings → User Permissions → …" }      a click path, on a quiet panel
 *   { button: "label", url: "https://…" }             button + visible URL
 *   { ol: ["first", "second"] }                        numbered list
 */

import {
  EMAIL_BUTTON, EMAIL_LIST, EMAIL_P, EMAIL_PANEL, EMAIL_SMALL, EMAIL_URL, emailLetter,
} from "../../lib/tool_email.js";

export const DEFAULT_FROM = "Hagen Simmons <hagen.simmons@hubricon.com>";

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// The one email look lives in lib/tool_email.js (Vercel ships lib/, not this file).
function htmlBlock(b) {
  if (b.p) return `  <p ${EMAIL_P}>${esc(b.p)}</p>`;
  if (b.path) return `  <p ${EMAIL_PANEL}>${esc(b.path)}</p>`;
  if (b.button) {
    return [
      `  <p style="margin:0 0 10px">`,
      `    <a href="${esc(b.url)}"`,
      `       ${EMAIL_BUTTON}>`,
      `      ${esc(b.button)}`,
      `    </a>`,
      `  </p>`,
      `  <p ${EMAIL_SMALL}><a href="${esc(b.url)}" ${EMAIL_URL}>${esc(b.url)}</a></p>`,
    ].join("\n");
  }
  if (b.ol) {
    const items = b.ol.map((i) => `    <li style="margin:0 0 10px">${esc(i)}</li>`).join("\n");
    return `  <ol ${EMAIL_LIST}>\n${items}\n  </ol>`;
  }
  throw new Error(`Unknown email block: ${JSON.stringify(b)}`);
}

export function renderHtml({ greeting, blocks }) {
  return emailLetter(greeting ? esc(greeting) : "", blocks.map(htmlBlock));
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
