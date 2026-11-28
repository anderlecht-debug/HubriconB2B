// Fakes for the self-serve checkout tests: a Supabase client that keeps its
// rows in memory, a Stripe client that records what it was asked, and a
// Resend that never leaves the process. Nothing here touches a network, a
// database or a card. Not a test file itself (node --test does not run it).
import { CHECKOUT_ENV } from "./checkout.js";

export const ENV = Object.fromEntries(CHECKOUT_ENV.map((k) => [k, `${k.toLowerCase()}_value`]));

// The unique constraints the real schema has and provisioning leans on.
const UNIQUE = {
  clients: [["contact_email"], ["stripe_customer_id"], ["stripe_subscription_id"]],
  client_emails: [["client_id", "kind", "ref_id"]],
  client_users: [["user_id", "client_id"]],
};
const DEFAULTS = {
  client_emails: () => ({ ref_id: "" }),
  client_users: () => ({ role: "member" }),
};
const DUPLICATE = { code: "23505", message: "duplicate key value violates unique constraint" };

let serial = 0;
const uuid = () => `00000000-0000-4000-8000-${String(++serial).padStart(12, "0")}`;

/**
 * fakeDb({ clients: [...] }): `db.store` holds the tables, `db.fail` maps
 * "table.op" (op: select, insert, update, upsert, delete) or "rpc.name" or
 * "auth.createUser" to an error message that call then answers with, and
 * `db.calls` lists every write in order.
 */
export function fakeDb(tables = {}, { users = [], sessions = {} } = {}) {
  const store = { intake_tokens: [], stripe_events: [], ...structuredClone(tables) };
  const db = { store, fail: {}, calls: [], users: structuredClone(users), sessions };
  const rows = (name) => (store[name] ||= []);
  const failing = (key) => (db.fail[key] ? { message: db.fail[key] } : null);

  const clash = (name, row, except = null) =>
    (UNIQUE[name] || []).some((cols) =>
      cols.every((c) => row[c] !== null && row[c] !== undefined) &&
      rows(name).some((r) => r !== except && cols.every((c) => r[c] === row[c])));

  db.from = (name) => {
    const q = { op: "select", filters: [], patch: null, added: null, cap: null, count: false, conflict: null };
    const match = (r) => q.filters.every((f) => f(r));
    const run = () => {
      const err = failing(`${name}.${q.op}`);
      if (err) return { data: null, error: err };
      if (q.op === "insert") {
        const made = [];
        for (const given of q.added) {
          const row = { id: uuid(), ...(DEFAULTS[name]?.() ?? {}), ...structuredClone(given) };
          if (clash(name, row)) return { data: null, error: DUPLICATE };
          made.push(row);
        }
        rows(name).push(...made);
        db.calls.push([`${name}.insert`, ...made]);
        return { data: structuredClone(made), error: null };
      }
      if (q.op === "upsert") {
        const cols = (q.conflict || "id").split(",").map((s) => s.trim());
        const out = [];
        for (const given of q.added) {
          const hit = rows(name).find((r) => cols.every((c) => r[c] === given[c]));
          if (hit) Object.assign(hit, structuredClone(given));
          else rows(name).push({ id: uuid(), ...(DEFAULTS[name]?.() ?? {}), ...structuredClone(given) });
          out.push(structuredClone(hit ?? rows(name).at(-1)));
        }
        db.calls.push([`${name}.upsert`, ...out]);
        return { data: out, error: null };
      }
      const hits = rows(name).filter(match);
      if (q.op === "update") {
        for (const r of hits) {
          if (clash(name, { ...r, ...q.patch }, r)) return { data: null, error: DUPLICATE };
        }
        for (const r of hits) Object.assign(r, structuredClone(q.patch));
        db.calls.push([`${name}.update`, q.patch, hits.length]);
        return { data: structuredClone(hits), error: null };
      }
      if (q.op === "delete") {
        store[name] = rows(name).filter((r) => !hits.includes(r));
        db.calls.push([`${name}.delete`, hits.length]);
        return { data: structuredClone(hits), error: null };
      }
      const shown = q.cap === null ? hits : hits.slice(0, q.cap);
      return q.count ? { data: null, count: hits.length, error: null } : { data: structuredClone(shown), error: null };
    };
    const one = (strict) => {
      const { data, error } = run();
      if (error) return { data: null, error };
      if (data.length > 1) return { data: null, error: { code: "PGRST116", message: "more than one row" } };
      if (data.length === 0 && strict) return { data: null, error: { code: "PGRST116", message: "no rows" } };
      return { data: data[0] ?? null, error: null };
    };
    const api = {
      select: (_cols, opts) => { if (opts?.head) q.count = true; return api; },
      insert: (row) => { q.op = "insert"; q.added = [].concat(row); return api; },
      upsert: (row, opts) => { q.op = "upsert"; q.added = [].concat(row); q.conflict = opts?.onConflict; return api; },
      update: (patch) => { q.op = "update"; q.patch = patch; return api; },
      delete: () => { q.op = "delete"; return api; },
      eq: (c, v) => { q.filters.push((r) => r[c] === v); return api; },
      neq: (c, v) => { q.filters.push((r) => r[c] !== v); return api; },
      in: (c, vs) => { q.filters.push((r) => vs.includes(r[c])); return api; },
      is: (c, v) => { q.filters.push((r) => (r[c] ?? null) === v); return api; },
      not: (c, _op, v) => { q.filters.push((r) => (r[c] ?? null) !== v); return api; },
      order: () => api,
      limit: (n) => { q.cap = n; return api; },
      maybeSingle: async () => one(false),
      single: async () => one(true),
      then: (resolve, reject) => Promise.resolve(run()).then(resolve, reject),
    };
    return api;
  };

  db.rpc = async (fn, args) => {
    const err = failing(`rpc.${fn}`);
    if (err) return { data: null, error: err };
    if (fn === "create_intake_token") {
      if (store.intake_tokens.some((t) => t.token_hash === args.p_token_hash)) return { data: null, error: DUPLICATE };
      const row = {
        id: uuid(), client_id: args.p_client_id, token_hash: args.p_token_hash,
        label: args.p_label ?? null, expires_at: args.p_expires_at ?? null, revoked_at: null,
      };
      store.intake_tokens.push(row);
      db.calls.push(["rpc.create_intake_token", row]);
      return { data: row.id, error: null };
    }
    if (fn === "record_stripe_event") {
      const fresh = !store.stripe_events.includes(args.p_event_id);
      if (fresh) store.stripe_events.push(args.p_event_id);
      return { data: fresh, error: null };
    }
    return { data: null, error: { code: "PGRST202", message: `Could not find the function ${fn}` } };
  };

  db.auth = {
    admin: {
      createUser: async ({ email }) => {
        const err = failing("auth.createUser");
        if (err) return { data: { user: null }, error: err };
        if (db.users.some((u) => u.email === email)) {
          return { data: { user: null }, error: { message: "A user with this email address has already been registered" } };
        }
        const user = { id: uuid(), email };
        db.users.push(user);
        db.calls.push(["auth.createUser", email]);
        return { data: { user }, error: null };
      },
      listUsers: async ({ page = 1, perPage = 50 } = {}) => {
        const err = failing("auth.listUsers");
        if (err) return { data: { users: [] }, error: err };
        return { data: { users: db.users.slice((page - 1) * perPage, page * perPage) }, error: null };
      },
    },
    getUser: async (jwt) => {
      const user = db.sessions[jwt];
      return user ? { data: { user }, error: null } : { data: { user: null }, error: { message: "invalid JWT" } };
    },
  };
  return db;
}

/** A paid Checkout Session as Stripe sends it on checkout.session.completed. */
export function paidSession(over = {}) {
  return {
    id: "cs_test_a1b2c3d4e5f6",
    object: "checkout.session",
    mode: "subscription",
    status: "complete",
    payment_status: "paid",
    customer: "cus_new1",
    subscription: "sub_new1",
    customer_details: { email: "Owner@Brand.com", name: "Dana Owner" },
    metadata: { hubricon_plan: "self_serve", hubricon_platform: "shopify" },
    ...over,
  };
}

/**
 * A Stripe that records. `sessions` maps a Checkout Session id to what
 * retrieve answers; `fail` maps "checkout.create", "checkout.retrieve",
 * "portal.create", "subscriptions.update" or "invoices.update" to a message.
 */
export function fakeStripe({ sessions = {}, fail = {}, url = "https://checkout.stripe.test/c/pay/cs_test_abc12345" } = {}) {
  const calls = [];
  const holds = [];
  const boom = (key) => { if (fail[key]) throw new Error(fail[key]); };
  return {
    calls,
    holds,
    checkout: {
      sessions: {
        create: async (params) => { calls.push(["checkout.create", params]); boom("checkout.create"); return { id: "cs_test_abc12345", url }; },
        retrieve: async (id) => {
          calls.push(["checkout.retrieve", id]);
          boom("checkout.retrieve");
          if (!sessions[id]) throw Object.assign(new Error(`No such checkout.session: ${id}`), { code: "resource_missing", statusCode: 404 });
          return sessions[id];
        },
      },
    },
    billingPortal: {
      sessions: {
        create: async (params) => {
          calls.push(["portal.create", params]);
          if (params.flow_data && fail["portal.flow"]) throw new Error(fail["portal.flow"]);
          boom("portal.create");
          return { id: "bps_test_1", url: "https://billing.stripe.test/p/session/bps_test_1" };
        },
      },
    },
    subscriptions: {
      update: async (id, params) => {
        calls.push(["subscriptions.update", id, params]);
        boom("subscriptions.update");
        return { id, ...params, current_period_end: 1796083200 };
      },
    },
    invoices: {
      update: async (id, params) => { holds.push([id, params]); boom("invoices.update"); return { id, ...params }; },
    },
  };
}

/** A Resend that answers 200 and keeps what it was sent. */
export function fakeResend({ status = 200 } = {}) {
  const sent = [];
  const fetchImpl = async (url, init) => {
    sent.push({ url, ...JSON.parse(init.body) });
    return new Response(JSON.stringify(status === 200 ? { id: `re_${sent.length}` } : { message: "resend is down" }), {
      status, headers: { "content-type": "application/json" },
    });
  };
  return { sent, fetchImpl };
}
