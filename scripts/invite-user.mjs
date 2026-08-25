/**
 * Give a client (or someone on their team) portal access.
 *
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
 *     npm run invite-user -- --email jane@acme.com --client acme@contact.com [--role member]
 *
 * Creates the auth user if needed (no password — they sign in with a magic
 * link at /portal) and links them to the client workspace. Every extra seat
 * is a retention thread: invite the ops lead and the bookkeeper too.
 */
import { parseArgs } from "node:util";
import { createClient } from "@supabase/supabase-js";

const missing = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"].filter((k) => !process.env[k]);
if (missing.length) {
  console.error(`Set ${missing.join(", ")} before running.`);
  process.exit(1);
}

const { values: args } = parseArgs({
  options: {
    email: { type: "string" },
    client: { type: "string" },
    role: { type: "string", default: "member" },
  },
});
if (!args.email || !args.client) {
  console.error("Usage: npm run invite-user -- --email person@company.com --client <client email or uuid prefix>");
  process.exit(1);
}
const email = args.email.trim().toLowerCase();

const db = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
  auth: { persistSession: false },
});

// resolve the client workspace
let q = db.from("clients").select("id, company_name, contact_email");
q = args.client.includes("@") ? q.eq("contact_email", args.client.toLowerCase()) : q.like("id", `${args.client}%`);
const { data: clients, error: clientError } = await q;
if (clientError || !clients?.length) {
  console.error(`No client matches "${args.client}"`);
  process.exit(1);
}
if (clients.length > 1) {
  console.error(`Ambiguous client: ${clients.map((c) => c.company_name).join(", ")}`);
  process.exit(1);
}
const client = clients[0];

// find-or-create the auth user (passwordless; portal magic link signs them in)
let userId;
const { data: created, error: createError } = await db.auth.admin.createUser({
  email,
  email_confirm: true,
});
if (!createError) {
  userId = created.user.id;
  console.log(`Created portal login for ${email}`);
} else {
  const { data: listed, error: listError } = await db.auth.admin.listUsers({ perPage: 1000 });
  const existing = listError ? null : listed.users.find((u) => u.email?.toLowerCase() === email);
  if (!existing) {
    console.error(`Could not create or find user: ${createError.message}`);
    process.exit(1);
  }
  userId = existing.id;
  console.log(`${email} already has a login — linking it.`);
}

const { error: linkError } = await db
  .from("client_users")
  .upsert({ user_id: userId, client_id: client.id, role: args.role }, { onConflict: "user_id,client_id" });
if (linkError) {
  console.error(`Linking failed: ${linkError.message}`);
  process.exit(1);
}

console.log(`
${email} now has ${args.role} access to ${client.company_name ?? client.contact_email}.

Tell them: go to https://www.hubricon.com/portal, enter this email,
and click the sign-in link that arrives. No password to remember.
`);
