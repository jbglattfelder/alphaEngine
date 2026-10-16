// Shared setup for the venue's e2e tests.
//
// Determinism: the engine is bit-deterministic for a given Config; the page's
// Date is frozen, and with ?e2e the page hands the same instant to the worker; the CDNs are replaced by pinned local copies; the market is
// advanced with the ?e2e step hook (exactly k ticks, paused), never by wall
// time. Two runs of a test therefore see the same pixels.
const fs = require("fs");
const path = require("path");
const { test: base, expect } = require("@playwright/test");

const PYO = process.env.PYODIDE_DIR || path.join(__dirname, "pyodide-cache");
const LWC = path.join(__dirname, "node_modules", "lightweight-charts", "dist",
  "lightweight-charts.standalone.production.js");
const FROZEN_NOW = new Date("2026-10-15T07:31:25Z");      // 09:31:25 in Zurich

const TYPES = { ".wasm": "application/wasm", ".js": "text/javascript", ".json": "application/json" };

async function routeCdns(ctx) {
  await ctx.route(/cdn\.jsdelivr\.net\/pyodide\/v0\.27\.7\/full\/(.*)$/, (route) => {
    const f = route.request().url().split("/full/")[1].split("?")[0];
    const p = path.join(PYO, f);
    if (!fs.existsSync(p)) return route.fulfill({ status: 404, body: `missing ${f}` });
    route.fulfill({ status: 200, body: fs.readFileSync(p),
      contentType: TYPES[path.extname(f)] || "application/octet-stream",
      headers: { "access-control-allow-origin": "*" } });
  });
  await ctx.route(/unpkg\.com\/lightweight-charts@4\.2\.0\//, (route) =>
    route.fulfill({ status: 200, body: fs.readFileSync(LWC), contentType: "text/javascript",
      headers: { "access-control-allow-origin": "*" } }));          // SRI needs CORS
}

const test = base.extend({
  // every page: pinned CDNs, frozen clock, console errors collected and asserted
  page: async ({ page }, use) => {
    const errors = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("worker", (w) => w.on("console", (m) => { if (m.type() === "error") errors.push("worker: " + m.text()); }));
    await routeCdns(page.context());
    await page.clock.setFixedTime(FROZEN_NOW);
    await use(page);
    expect(errors, "console errors").toEqual([]);
  },
});

const LOGIN = { user: "liquidity", pass: "engine" };
const DEFAULTS = { name: LOGIN.user, arm: "NNNN", n: 150, K: 1000000, tp: 1, sl: 1, c: 0.004, q: 8, seed: 9, eur: 50000, rcc: 500 };

async function signIn(page, name = LOGIN.user, pass = LOGIN.pass, query = "?e2e") {
  await page.goto("./" + query);
  await page.fill("#login-name", name);
  await page.fill("#login-pass", pass);
  await page.click("#btn-login");
  await expect(page.locator("#screen-config")).toBeVisible();
}

async function configure(page, cfg = {}) {
  const c = { ...DEFAULTS, ...cfg };
  if (c.arm !== "NNNN") await page.click(`#cfg-arm button[data-v="${c.arm}"]`);
  for (const [id, v] of [["n", c.n], ["K", c.K], ["tp", c.tp], ["sl", c.sl], ["c", c.c],
    ["q", c.q], ["seed", c.seed], ["eur", c.eur], ["rcc", c.rcc]])
    await page.fill(`#cfg-${id}`, String(v));
}

async function launch(page) {
  await page.click("#btn-launch");
  await expect(page.locator("#screen-trade")).toBeVisible({ timeout: 120_000 });
  await page.waitForFunction(() => window.__rpm);
  await page.evaluate(() => window.__rpm.sync());
}

async function openMarket(page, cfg = {}) {
  await signIn(page, cfg.name);
  await configure(page, cfg);
  await launch(page);
}

const step = (page, k) => page.evaluate((k) => window.__rpm.step(k), k);
const sync = (page) => page.evaluate(() => window.__rpm.sync());

async function quick(page, which) {              // BID | MID | ASK button
  await page.click(`.quick a[data-q="${which}"]`);
  return parseFloat(await page.inputValue("#f-price"));
}

async function order(page, { side, kind, qty, price, unit }) {
  await page.click(side === "buy" ? "#side-buy" : "#side-sell");
  await page.click(`.kinds button[data-kind="${kind}"]`);
  if (unit && (await page.textContent("#f-unit")) !== unit) await page.click("#f-unit");
  if (price != null) await page.fill("#f-price", String(price));
  await page.fill("#f-qty", String(qty));
  await page.click("#f-submit");
  await sync(page);
}

// The reference session the screenshots are taken of: seed 9, NNNN, n = 150,
// 300 ticks, then one of each order type, then 200 more ticks.
async function referenceSession(page) {
  await openMarket(page);
  await step(page, 300);
  const bid = await quick(page, "bid");
  await order(page, { side: "buy", kind: "limit", qty: 5, price: (bid * 0.99).toFixed(2) });
  await order(page, { side: "buy", kind: "market", qty: 2 });
  await order(page, { side: "buy", kind: "market", qty: 300, unit: "EUR" });
  await order(page, { side: "sell", kind: "limit", qty: 20, price: "118.00" });
  await order(page, { side: "sell", kind: "market", qty: 3 });
  await step(page, 200);
}

module.exports = { test, expect, LOGIN, DEFAULTS, signIn, configure, launch, openMarket, step, sync, quick, order, referenceSession };
