// Behaviour regression: what the venue does, independent of how it looks.
const { test, expect, signIn, configure, launch, openMarket, step, sync, quick, order } = require("./fixtures");

const num = async (page, sel) => parseFloat((await page.textContent(sel)).replace(/[^0-9.\-]/g, ""));
const tick = (page) => num(page, "#hdr-tick");

test("sign-in needs liquidity / engine", async ({ page }) => {
  await page.goto("./?e2e");
  for (const [u, p] of [["liquidity", "wrong"], ["someone", "engine"], ["", ""]]) {
    await page.fill("#login-name", u);
    await page.fill("#login-pass", p);
    await page.click("#btn-login");
    await expect(page.locator("#login-err")).toHaveText("Wrong username or password");
    await expect(page.locator("#screen-login")).toBeVisible();
  }
  await page.fill("#login-pass", "x");
  await expect(page.locator("#login-err")).toHaveText("");          // typing clears it
  await page.fill("#login-name", "liquidity");
  await page.fill("#login-pass", "engine");
  await page.locator("#login-pass").press("Enter");
  await expect(page.locator("#screen-config")).toBeVisible();
  await expect(page.locator("#avatar")).toHaveText("L");
});

test("configure validates and clears errors", async ({ page }) => {
  await signIn(page);
  await configure(page, { eur: 800000 });
  await page.click("#btn-launch");
  await expect(page.locator("#cfg-err")).toHaveText("your allocation exceeds 75% of K");
  await page.fill("#cfg-eur", "50000");
  await expect(page.locator("#cfg-err")).toHaveText("");
  for (const n of [0, 10001]) {
    await configure(page, { n });
    await page.click("#btn-launch");
    await expect(page.locator("#cfg-err")).toHaveText("n must be between 1 and 10,000 agents per side");
    await expect(page.locator("#screen-config")).toBeVisible();
  }
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

test("n = 10,000 per side opens", async ({ page }) => {
  await openMarket(page, { n: 10000 });
  await expect(page.locator("#hdr-alive")).toHaveText("20000 / 20000");
  await step(page, 3);
  expect(await tick(page)).toBe(3);
});

test("a market starts playing by itself at 6 ticks/s", async ({ page }) => {
  await signIn(page, undefined, undefined, "?e2e&autoplay");
  await launch(page);
  await expect(page.locator("#speed-val")).toHaveText("6");
  await expect(page.locator("#play-icon")).toHaveAttribute("d", "M7 5h4v14H7zM13 5h4v14h-4z");   // pause glyph
  await expect.poll(() => tick(page), { timeout: 15_000 }).toBeGreaterThan(10);
  await page.click("#btn-play");
});

test("one arrow per trade, however many makers it sweeps", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  await order(page, { side: "buy", kind: "market", qty: 30 });
  await page.click(".tabs[data-group=bottom] button[data-tab=fills]");
  expect(await page.locator("#t-fills tr").count()).toBeGreaterThan(1);    // several makers…
  expect(await page.evaluate(() => window.__rpm.markers())).toBe(1);       // …one arrow
  await order(page, { side: "sell", kind: "market", qty: 10 });
  expect(await page.evaluate(() => window.__rpm.markers())).toBe(2);
});

test("volume bars: one per tick, adding up to the session volume", async ({ page }) => {
  await openMarket(page);
  await step(page, 500);
  await order(page, { side: "buy", kind: "market", qty: 3 });
  await step(page, 100);
  const vols = await page.evaluate(() => window.__rpm.volumes());
  expect(vols.length).toBe(601);                                            // tick 0 … 600
  const total = vols.reduce((a, b) => a + b, 0);
  expect(Math.abs(total - (await num(page, "#hdr-vol")))).toBeLessThan(0.01);
});

test("the price chart zooms out to the whole session", async ({ page }) => {
  await openMarket(page);
  await step(page, 6000);
  const box = await page.locator("#chart").boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 60; i++) await page.mouse.wheel(0, 400);
  const r = await page.evaluate(() => window.__rpm.visible());
  expect(r.to - r.from).toBeGreaterThanOrEqual(6000);
});

test("going to the depth chart resets the price chart's zoom and scroll", async ({ page }) => {
  await openMarket(page);
  await step(page, 3000);
  const fresh = await page.evaluate(() => window.__rpm.visible());
  const box = await page.locator("#chart").boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 30; i++) await page.mouse.wheel(0, 400);            // zoom far out
  await page.mouse.down();                                                  // and drag the curve away
  await page.mouse.move(box.x + box.width - 5, box.y + box.height / 2, { steps: 10 });
  await page.mouse.up();
  const lost = await page.evaluate(() => window.__rpm.visible());
  expect(lost.to - lost.from).toBeGreaterThan(2 * (fresh.to - fresh.from));
  await page.click(".tabs[data-group=chart] button[data-tab=depth]");
  await page.click(".tabs[data-group=chart] button[data-tab=price]");
  const back = await page.evaluate(() => window.__rpm.visible());
  expect(back.from).toBeCloseTo(fresh.from, 0);
  expect(back.to).toBeCloseTo(fresh.to, 0);
});

test("every file is fetched with the deploy's version stamp", async ({ page }) => {
  const seen = [];
  await page.context().route(/\/(js|css|py)\/[^/]+\.(js|css|py)(\?|$)|simulation_mvp\.py/, (route) => {
    seen.push(new URL(route.request().url()));
    route.fallback();
  });
  await openMarket(page);
  const names = seen.map((u) => u.pathname.split("/").pop()).sort();
  expect(names).toEqual(["app.css", "app.js", "simulation_mvp.py", "venue_wrapper.py", "worker.js"]);
  for (const u of seen) expect(u.searchParams.get("v"), u.pathname).toBe("__BUILD__");   // replaced at deploy
});

test("open limit orders are dotted lines without axis labels, gone when cancelled", async ({ page }) => {
  await openMarket(page);
  await step(page, 300);
  for (const px of ["150.00", "150.50", "151.00"]) await order(page, { side: "sell", kind: "limit", qty: 2, price: px });
  await order(page, { side: "buy", kind: "limit", qty: 2, price: "60.00" });
  const lines = await page.evaluate(() => window.__rpm.orderLines());
  expect(lines.map((l) => l.price).sort()).toEqual([150, 150.5, 151, 60].sort());
  for (const l of lines) {
    expect(l.axisLabelVisible).toBe(false);
    expect(l.title).toBe("");
    expect(l.lineStyle).toBe(1);                                   // LineStyle.Dotted
  }
  await page.click("#btn-cancel-all");
  await sync(page);
  expect(await page.evaluate(() => window.__rpm.orderLines())).toEqual([]);
});

test("amount slider labels: 0 % to Max, each sets its own value", async ({ page }) => {
  await openMarket(page);
  await step(page, 100);
  await page.click("#side-sell");                                   // 500 RCC available
  await expect(page.locator(".pct-ticks a")).toHaveText(["0%", "25%", "50%", "75%", "Max"]);
  for (const [p, q] of [["50", "250"], ["0", "0"], ["25", "125"], ["100", "500"]]) {
    await page.click(`.pct-ticks a[data-p="${p}"]`);
    expect(await page.inputValue("#f-pct")).toBe(p);
    expect(parseFloat(await page.inputValue("#f-qty"))).toBeCloseTo(+q, 3);
  }
  // each middle label is centred over the slider position it sets
  const slider = await page.locator("#f-pct").boundingBox();
  for (const p of [25, 50, 75]) {
    const b = await page.locator(`.pct-ticks a[data-p="${p}"]`).boundingBox();
    const want = slider.x + 8 + (slider.width - 16) * p / 100;
    expect(Math.abs(b.x + b.width / 2 - want)).toBeLessThan(1.5);
  }
});
