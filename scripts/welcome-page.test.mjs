// /welcome, the page after the yes, for a Shopify seller: the seat it asks for is one Shopify
// actually offers, with the permissions the work needs and no more; the ad accounts are asked for
// separately, because a Shopify user cannot reach them; later months' files reach us the way they
// really do; and nothing is said to be watched that no code watches (audit of 2026-10-01).
//   node --test scripts/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (p) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const html = read("welcome.html");
const words = (h) => h.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>|<!--[\s\S]*?-->/g, " ")
  .replace(/<[^>]+>/g, " ").replace(/&amp;/g, "&").replace(/\s+/g, " ").replace(/ ([,.;:)])/g, "$1");
const page = words(html);
const shopify = words(html.match(/<div id="seat-shopify">([\s\S]*?)\n    <\/div>\n/)[1]);

test("the Shopify seat is a staff account with a role of exactly these permissions", () => {
  assert.doesNotMatch(page, /collaborator/i, "a collaborator request needs a Shopify Partner organisation nothing shows exists");
  assert.match(shopify, /Add one staff account\. Shopify allows them on the Grow, Advanced and Plus plans\./);
  assert.match(shopify, /Settings → Users → Roles → Add role/);
  const perms = [...html.match(/<div id="seat-shopify">[\s\S]*?<ul class="perm">([\s\S]*?)<\/ul>/)[1].matchAll(/<li>([\s\S]*?)<\/li>/g)].map(([, li]) => words(li).trim());
  assert.deepEqual(perms, [
    "Orders: View, Export",
    "Products: View, View cost, Edit price, Export (Edit price is how a price step happens)",
    "Discounts: View, create, and delete",
    "Analytics & reports: Reports",
  ]);
  assert.match(shopify, /Everything else stays off\. Finance, Customers, Settings, apps and every other edit\./);
  assert.match(shopify, /Settings → Users → Add users → Admin user → the email above → assign the Hubricon role/);
  assert.match(shopify, /On Shopify's Basic plan Shopify allows no staff accounts/, "Basic and Starter allow no staff accounts at all");
});

test("the ad accounts are asked for on their own, and later months' files arrive the way they really do", () => {
  assert.match(shopify, /A Shopify user cannot reach Meta or Google/);
  assert.match(shopify, /Meta: we send you our business portfolio ID\./);
  assert.match(shopify, /Not full control\./);
  assert.match(shopify, /Google Ads: Admin → Access and security → the plus button → the email above → Standard\./);
  assert.match(shopify, /it can also see billing, which we do not use/, "Standard is not billing-free, and the page says so");
  assert.match(page, /we download them through the seat ourselves, by hand/);
  assert.match(shopify, /Payouts sit under Finance, which this user cannot open, so a payouts export always comes from you, on your upload page\./);
});

test("nothing is said to be watched on Shopify that no code watches", () => {
  assert.doesNotMatch(page, /conversion rate[^.]*watched|watched[^.]*conversion/i, "nothing ingests a Shopify conversion rate");
  assert.match(page, /on Shopify a step is read on your orders/);
  assert.doesNotMatch(page, /through one user with narrow permissions/, "on Shopify, ads do not change through the store's user");
  assert.match(page, /comes back to your bank\./);
  assert.doesNotMatch(page, /comes back to your bank within/i, "no deadline the code does not keep");
  // the both-seller line rests on the Briefs naming the store (another session's change)
  assert.match(page, /the briefs say which one a number came from/);
});

test("revoking: the real steps on each platform, and what pauses", () => {
  assert.match(page, /Shopify: Settings → Users → the Hubricon user → Actions → Remove\./);
  assert.match(page, /Meta: Settings → Users → Partners → remove us\./);
  assert.match(page, /Without the store seat the service pauses until it is back; without the ad access, only ad moves do\./);
  assert.doesNotMatch(page, /Collaborators → remove/);
});
