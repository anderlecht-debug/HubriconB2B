/**
 * Give a client (or someone on their team) portal access.
 *
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
 *     npm run invite-user -- --email jane@acme.com --client acme@contact.com [--role member]
 *
 * --client is the client's contact email, its full id, or the first few
 * characters of its id (as `hubricon` prints them).
 *
 * Creates the auth user if needed (no password — they sign in with a magic
 * link at /portal) and links them to the client workspace. Every extra seat
 * is a retention thread: invite the ops lead and the bookkeeper too.
 */
import { parseArgs } from "node:util";
import { pathToFileURL } from "node:url";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const PREFIX = /^[0-9a-f-]{4,36}$/i;

/**
 * The clients `--client` names. clients.id is a uuid, and Postgres has no LIKE
 * on a uuid, so `.like("id", "ab12%")` failed for every prefix; a full id is
 * matched exactly and a prefix is matched here, over the client list.
 */
export async function findClients(db, ref) {
  const arg = String(ref ?? "").trim();
  const cols = "id, company_name, contact_email";
  if (arg.includes("@")) {
    const { data, error } = await db.from("clients").select(cols).eq("contact_email", arg.toLowerCase());
    return { clients: data ?? [], error };
  }
  if (UUID.test(arg)) {
    const { data, error } = await db.from("clients").select(cols).eq("id", arg.toLowerCase());
    return { clients: data ?? [], error };
  }
  if (!PREFIX.test(arg)) return { clients: [], error: null };
  const { data, error } = await db.from("clients").select(cols).range(0, 9999);
  const prefix = arg.toLowerCase();
  return { clients: (data ?? []).filter((c) => String(c.id).toLowerCase().startsWith(prefix)), error };
}

async function main() {
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
    console.error("Usage: npm run invite-user -- --email person@company.com --client <client email, id or id prefix>");
    process.exit(1);
  }
  const email = args.email.trim().toLowerCase();

  const { createClient } = await import("@supabase/supabase-js");
  const db = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false },
  });

  // resolve the client workspace
  const { clients, error: clientError } = await findClients(db, args.client);
  if (clientError) {
    console.error(`Client lookup failed: ${clientError.message}`);
    process.exit(1);
  }
  if (!clients.length) {
    console.error(`No client matches "${args.client}"`);
    process.exit(1);
  }
  if (clients.length > 1) {
    console.error(`Ambiguous client: ${clients.map((c) => `${c.company_name ?? c.contact_email} (${c.id})`).join(", ")}`);
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
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
