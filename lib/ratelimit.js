/**
 * A sliding-window counter per key, in memory. On Vercel this lives as long
 * as the function instance does, which is minutes to hours — enough to stop a
 * script hammering one instance, and nothing more. The durable limit on the
 * capture (per hashed IP and per email, over a day) is a count in tool_runs,
 * in api/quick.js, because a table survives a cold start and a Map does not.
 */
export class SlidingWindow {
  constructor({ limit, windowMs, maxKeys = 5000 }) {
    this.limit = limit;
    this.windowMs = windowMs;
    this.maxKeys = maxKeys;
    this.hits = new Map();
  }

  /** Record one hit for `key`; says whether it was allowed and when to retry if not. */
  hit(key, now = Date.now()) {
    const cutoff = now - this.windowMs;
    const arr = (this.hits.get(key) || []).filter((t) => t > cutoff);
    if (arr.length >= this.limit) {
      this.hits.set(key, arr);
      return { ok: false, remaining: 0, retryAfterMs: Math.max(1, arr[0] + this.windowMs - now) };
    }
    arr.push(now);
    this.hits.set(key, arr);
    if (this.hits.size > this.maxKeys) this.prune(now);
    return { ok: true, remaining: this.limit - arr.length, retryAfterMs: 0 };
  }

  prune(now = Date.now()) {
    const cutoff = now - this.windowMs;
    for (const [k, arr] of this.hits) {
      const kept = arr.filter((t) => t > cutoff);
      if (kept.length) this.hits.set(k, kept);
      else this.hits.delete(k);
    }
  }
}

/** The caller's address as the edge reports it. Vercel sets x-forwarded-for; the first hop is the client. */
export function clientIp(headers) {
  const xff = headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return headers.get("x-real-ip") || headers.get("cf-connecting-ip") || "unknown";
}
