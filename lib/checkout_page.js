/**
 * The few small pages the card offer answers with when there is no /start
 * page to say it: a pay button pressed as a plain form while payment is not
 * switched on, and the cancel link in the welcome email. Same look as the
 * consent page (lib/consent_page.js): layout and tokens only, every colour
 * from /assets/hubricon.css.
 */
import { esc, STYLE, MARK } from "./consent_page.js";

export { esc };

/**
 * One small page. `lines` are plain sentences (escaped here); `action` is
 * ready-made HTML the caller built with esc().
 */
export function notice(status, title, lines = [], action = "") {
  const body = `<h1>${esc(title)}</h1>${lines.map((l) => `<p class="sub">${esc(l)}</p>`).join("")}${action}`;
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8">` +
      `<meta name="viewport" content="width=device-width,initial-scale=1">` +
      `<meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>${esc(title)} · Hubricon</title>` +
      `<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>` +
      `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400;14..32,600&display=swap">` +
      `<link rel="stylesheet" href="/assets/hubricon.css">` +
      `<style>${STYLE}</style></head><body><div class="wrap">${MARK}${body}</div></body></html>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } }
  );
}

export const backLink = (href, words) => `<p class="back"><a href="${esc(href)}">${esc(words)}</a></p>`;
