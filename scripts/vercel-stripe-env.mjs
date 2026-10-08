/**
 * Copy the Stripe values from .env into the website (Vercel), then redeploy so
 * they take effect. Prints names and outcomes only, never a value.
 *
 *   npm run vercel:stripe
 *
 * STRIPE_SECRET_KEY places the webhook's hold on each retainer invoice, so it
 * must be the account's live key; STRIPE_WEBHOOK_SECRET must be the signing
 * secret of the endpoint `npm run stripe:setup` made (it writes it into .env).
 * The redeploy rebuilds the commit already in production: no code ships.
 */
const PROJECT = "hubricon-b2-b";
const KEYS = ["STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"];
const token = process.env.VERCEL_TOKEN;

const missing = ["VERCEL_TOKEN", ...KEYS].filter((k) => !process.env[k]);
if (missing.length) {
  console.error(`Missing from .env: ${missing.join(", ")}. Nothing was changed.`);
  process.exit(1);
}
if (!/^(sk|rk)_live_/.test(process.env.STRIPE_SECRET_KEY)) {
  console.error("STRIPE_SECRET_KEY in .env is not a live key; the website bills real clients. Nothing was changed.");
  process.exit(1);
}

async function api(path, init = {}) {
  const res = await fetch(`https://api.vercel.com${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(init.headers || {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`${res.status} ${body.error?.message || "no message"}`);
  return body;
}

const project = await api(`/v9/projects/${PROJECT}`);
const envs = (await api(`/v9/projects/${project.id}/env`)).envs || [];
let failed = false;
for (const key of KEYS) {
  const existing = envs.find((e) => e.key === key && (e.target || []).includes("production"));
  try {
    if (existing) {
      await api(`/v9/projects/${project.id}/env/${existing.id}`, {
        method: "PATCH", body: JSON.stringify({ value: process.env[key] }),
      });
      console.log(`  ok   ${key} replaced (${(existing.target || []).join(", ")})`);
    } else {
      await api(`/v10/projects/${project.id}/env`, {
        method: "POST",
        body: JSON.stringify({ key, value: process.env[key], type: "sensitive", target: ["production"] }),
      });
      console.log(`  ok   ${key} added (production)`);
    }
  } catch (err) {
    failed = true;
    console.log(`  !!   ${key} not set: ${err.message}`);
  }
}
if (failed) {
  console.log("\nNot redeployed, because a value did not land. Nothing else was changed.");
  process.exit(1);
}

const latest = (await api(`/v6/deployments?projectId=${project.id}&target=production&state=READY&limit=1`))
  .deployments?.[0];
if (!latest) {
  console.log("\nValues set. No ready production deployment found to rebuild: Vercel → Deployments → Redeploy.");
  process.exit(1);
}
try {
  const next = await api(`/v13/deployments?forceNew=1`, {
    method: "POST",
    body: JSON.stringify({ name: PROJECT, deploymentId: latest.uid, target: "production" }),
  });
  console.log(`\nRedeploying ${latest.meta?.githubCommitSha?.slice(0, 7) || latest.uid} with the new values: ` +
              `${next.id} (${next.readyState || "queued"}). Live in about a minute.`);
} catch (err) {
  console.log(`\nValues set, but the redeploy was refused (${err.message}): Vercel → Deployments → Redeploy.`);
  process.exit(1);
}
