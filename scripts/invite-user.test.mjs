import { test } from "node:test";
import assert from "node:assert/strict";
import { findClients } from "./invite-user.mjs";

const ROWS = [
  { id: "3f2a9c10-1111-4aaa-8bbb-000000000001", company_name: "Acme Goods", contact_email: "jane@acme.com" },
  { id: "3f2a0000-2222-4aaa-8bbb-000000000002", company_name: "Birch & Co", contact_email: "sam@birch.co" },
  { id: "9d00e7aa-3333-4aaa-8bbb-000000000003", company_name: "Cedar", contact_email: "lee@cedar.io" },
];

// clients.id is a uuid: Postgres refuses LIKE on it, the way the old lookup failed.
function fakeDb() {
  return {
    from() {
      const filters = [];
      const q = {
        select() { return q; },
        eq(k, v) { filters.push((r) => r[k] === v); return q; },
        range() { return q; },
        like(k) {
          q.failed = { message: `operator does not exist: uuid ~~ unknown (${k})` };
          return q;
        },
        then(resolve) {
          return Promise.resolve(q.failed ? { data: null, error: q.failed } : { data: ROWS.filter((r) => filters.every((f) => f(r))), error: null }).then(resolve);
        },
      };
      return q;
    },
  };
}

test("an id prefix finds its client without LIKE on the uuid column", async () => {
  const { clients, error } = await findClients(fakeDb(), "9d00");
  assert.equal(error, null);
  assert.deepEqual(clients.map((c) => c.company_name), ["Cedar"]);
});

test("a prefix two clients share is ambiguous, not a guess", async () => {
  const { clients } = await findClients(fakeDb(), "3F2A");
  assert.equal(clients.length, 2);
});

test("a full id and a contact email are matched exactly", async () => {
  assert.deepEqual((await findClients(fakeDb(), ROWS[1].id.toUpperCase())).clients.map((c) => c.company_name), ["Birch & Co"]);
  assert.deepEqual((await findClients(fakeDb(), "Jane@Acme.com")).clients.map((c) => c.company_name), ["Acme Goods"]);
});

test("anything that cannot be an id matches nobody", async () => {
  assert.deepEqual((await findClients(fakeDb(), "acme")).clients, []);
  assert.deepEqual((await findClients(fakeDb(), "3f")).clients, [], "too short to mean one client");
});
