// Behaviour regression: what the venue does, independent of how it looks.
const { test, expect, signIn, configure, launch, openMarket, step, sync, quick, order } = require("./fixtures");

const num = async (page, sel) => parseFloat((await page.textContent(sel)).replace(/[^0-9.\-]/g, ""));
const tick = (page) => num(page, "#hdr-tick");

test("sign-in shows the name's initial; configure validates and clears errors", async ({ page }) => {
  await signIn(page, "ada");
  await expect(page.locator("#avatar")).toHaveText("A");
  await configure(page, { eur: 800000 });
  await page.click("#btn-launch");
  await expect(page.locator("#cfg-err")).toHaveText("your allocation exceeds 75% of K");
  await page.fill("#cfg-eur", "50000");
  await expect(page.locator("#cfg-err")).toHaveText("");
  await configure(page, { n: 0 });
  await page.click("#btn-launch");
  await expect(page.locator("#cfg-err")).not.toHaveText("");
  await expect(page.locator("#screen-config")).toBeVisible();
});

test("PFCF note and arm label", async ({ page }) => {
  await signIn(page);
  await page.click('#cfg-arm button[data-v="PFCF"]');
  await expect(page.locator("#cfg-band-note")).toHaveText("identical for every agent");
  await page.click('#cfg-arm button[data-v="NNNN"]');
  await expect(page.locator("#cfg-band-note")).toHaveText("mean of per-agent draws, cv 0.3");
  await page.click('#cfg-arm button[data-v="PFCF"]');
  await launch(page);
  await expect(page.locator("#hdr-arm")).toHaveText("PFCF");
});

test("market opens at x0 = 100, tick 0, with the allocation", async ({ page }) => {
  await openMarket(page);
  expect(await tick(page)).toBe(0);
  await expect(page.locator("#hdr-last")).toHaveText("100.00");
  await expect(page.locator("#a-eur")).toHaveText("50,000.00");
  await expect(page.locator("#a-rcc")).toHaveText("500.0000");
  await expect(page.locator("#hdr-alive")).toHaveText("300 / 300");
});

test("play, pause, space bar and the speed dial", async ({ page }) => {
  await openMarket(page);
  for (const [v, label] of [[0, "1"], [37, "10"], [100, "500"]]) {
    await page.locator("#speed").fill(String(v));
    await expect(page.locator("#speed-val")).toHaveText(label);
  }
  await page.click("#btn-play");
  await expect.poll(() => tick(page), { timeout: 15_000 }).toBeGreaterThan(50);
  await page.click("#btn-play");                                   // pause
  await sync(page);
  const t = await tick(page);
  await page.waitForTimeout(800);
  expect(await tick(page)).toBe(t);
  await page.locator("body").click({ position: { x: 5, y: 900 } });
  await page.keyboard.press("Space");                              // play again
  await expect.poll(() => tick(page), { timeout: 15_000 }).toBeGreaterThan(t);
  await page.keyboard.press("Space");
});

test("same seed, same market", async ({ page }) => {
  await openMarket(page);
  await step(page, 400);
  const a = [await page.textContent("#hdr-last"), await page.textContent("#hdr-vol")];
  page.once("dialog", (d) => d.accept());
  await page.click("#btn-new");
  await expect(page.locator("#screen-config")).toBeVisible();
  await launch(page);
  await step(page, 400);
  expect([await page.textContent("#hdr-last"), await page.textContent("#hdr-vol")]).toEqual(a);
});

test("New market asks first; dismissing keeps the market", async ({ page }) => {
  await openMarket(page);
  page.once("dialog", (d) => d.dismiss());
  await page.click("#btn-new");
  await expect(page.locator("#screen-trade")).toBeVisible();
  page.once("dialog", (d) => d.accept());
  await page.click("#btn-new");
  await expect(page.locator("#screen-config")).toBeVisible();
});

test("limit order rests, shows as open, cancels; cancel all", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  await order(page, { side: "sell", kind: "limit", qty: 5, price: "150.00" });
  await order(page, { side: "buy", kind: "limit", qty: 5, price: "50.00" });
  await expect(page.locator("#cnt-open")).toHaveText("2");
  await expect(page.locator("#t-open tr")).toHaveCount(2);
  await expect(page.locator("#f-avail")).toHaveText("49,750.00 EUR");      // 250 EUR locked
  await page.locator("#t-open [data-cancel]").first().click();
  await sync(page);
  await expect(page.locator("#cnt-open")).toHaveText("1");
  await page.click("#btn-cancel-all");
  await sync(page);
  await expect(page.locator("#cnt-open")).toHaveText("0");
  await expect(page.locator("#e-open")).toBeVisible();
  await page.click(".tabs[data-group=bottom] button[data-tab=hist]");
  await expect(page.locator("#t-hist tr")).toHaveCount(2);
  await expect(page.locator("#t-hist .st.cancelled")).toHaveCount(2);
});

test("market order fills as taker and lands in trade history", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  await order(page, { side: "sell", kind: "market", qty: 1 });
  await expect(page.locator(".toast.ok").last()).toContainText("Sell market filled: 1.0000 RCC");
  await page.click(".tabs[data-group=bottom] button[data-tab=fills]");
  await expect(page.locator("#t-fills tr").first()).toContainText("taker");
  await expect(page.locator("#a-rcc")).toHaveText("499.0000");
});

test("rejections and form validation", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  await order(page, { side: "sell", kind: "market", qty: 99999 });
  await expect(page.locator(".toast.bad").last()).toHaveText("Sell market rejected: insufficient RCC");
  await order(page, { side: "buy", kind: "limit", qty: 99999, price: "100.00" });
  await expect(page.locator(".toast.bad").last()).toHaveText("Buy limit rejected: insufficient EUR");
  await page.fill("#f-qty", "");
  await page.click("#f-submit");
  await expect(page.locator(".toast.bad").last()).toHaveText("Enter an amount");
  await page.fill("#f-price", "");
  await page.fill("#f-qty", "1");
  await page.click("#f-submit");
  await expect(page.locator(".toast.bad").last()).toHaveText("Enter a limit price");
});

test("order form helpers: book click, BID/MID/ASK, percent, unit switch", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  const row = page.locator(".bk-side .bk-row").first();
  const p = parseFloat(await row.getAttribute("data-p"));
  await page.click('.kinds button[data-kind="market"]');
  await row.click();
  await expect(page.locator('.kinds button[data-kind="limit"]')).toHaveClass(/on/);
  expect(parseFloat(await page.inputValue("#f-price"))).toBeCloseTo(p, 2);
  const bid = await quick(page, "bid"), ask = await quick(page, "ask"), mid = await quick(page, "mid");
  expect(mid).toBeGreaterThanOrEqual(Math.min(bid, ask) - 0.01);
  expect(mid).toBeLessThanOrEqual(Math.max(bid, ask) + 0.01);
  await page.click("#side-sell");
  await page.click('.pct-ticks a[data-p="100"]');
  expect(parseFloat(await page.inputValue("#f-qty"))).toBeLessThanOrEqual(500);
  await expect(page.locator("#f-unit")).toBeDisabled();             // sell / limit: RCC only
  await page.click("#side-buy");
  await page.click('.kinds button[data-kind="market"]');
  await expect(page.locator("#f-unit")).toBeEnabled();
  await page.click("#f-unit");
  await expect(page.locator("#f-unit")).toHaveText("EUR");
  await page.click('.kinds button[data-kind="limit"]');
  await expect(page.locator("#f-unit")).toHaveText("RCC");
});

test("PnL panel adds up: realised + unrealised = total", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  await order(page, { side: "buy", kind: "market", qty: 5 });
  await step(page, 200);
  await order(page, { side: "sell", kind: "market", qty: 2 });
  await step(page, 100);
  const r = await num(page, "#a-real"), u = await num(page, "#a-unreal"), t = await num(page, "#a-total");
  const sgn = async (sel) => ((await page.textContent(sel)).trim().startsWith("−") ? -1 : 1);
  expect(Math.abs((await sgn("#a-real")) * r + (await sgn("#a-unreal")) * u - (await sgn("#a-total")) * t)).toBeLessThan(0.011);
});

test("no horizontal scroll at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openMarket(page);
  await step(page, 100);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
});
