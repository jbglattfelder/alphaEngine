// Visual regression: every screen and tab of the venue, pixel for pixel.
// A difference fails the test; intended changes are re-baselined explicitly
// (npm run update) and the changed images are listed in the commit.
const path = require("path");
const { test, expect, signIn, configure, openMarket, step, sync, quick, referenceSession } = require("./fixtures");

const STYLE = path.join(__dirname, "screenshot.css");
const shot = (opts = {}) => ({ stylePath: STYLE, ...opts });

// Park the pointer in the top-left corner first: hover changes pixels (the
// number spinner, row highlights), so where the last click left it must not matter.
async function snap(page, target, name, opts) {
  await page.mouse.move(1, 1);
  await expect.soft(target).toHaveScreenshot(name, opts);
}

const DESKTOP = { width: 1600, height: 960 };
const TABLET = { width: 1024, height: 900 };
const PHONE = { width: 390, height: 844 };

test.describe("pre-trade screens", () => {
  for (const [label, vp] of [["desktop", DESKTOP], ["phone", PHONE]]) {
    test(`sign-in, ${label}`, async ({ page }) => {
      await page.setViewportSize(vp);
      await page.goto("./?e2e");
      await snap(page, page, `signin-${label}.png`, shot({ fullPage: true }));
    });

    test(`configure, ${label}`, async ({ page }) => {
      await page.setViewportSize(vp);
      await signIn(page);
      await snap(page, page, `config-${label}.png`, shot({ fullPage: true }));
    });
  }

  test("configure, PFCF selected and allocation over the cap", async ({ page }) => {
    await signIn(page);
    await configure(page, { arm: "PFCF", eur: 800000 });
    await page.click("#btn-launch");
    await expect.soft(page.locator("#cfg-err")).toHaveText("your allocation exceeds 75% of K");
    await snap(page, page, "config-pfcf-over-cap.png", shot({ fullPage: true }));
  });

  test("loading screen", async ({ page }) => {
    // hold numpy back so the loading card stays up for the shot
    let release;
    const held = new Promise((r) => (release = r));
    await page.context().route(/numpy-.*\.whl$/, async (route) => { await held; route.fallback(); });
    await signIn(page);
    await page.click("#btn-launch");
    await expect.soft(page.locator("#loading-msg")).toHaveText("Loading numpy…", { timeout: 60_000 });
    await snap(page, page, "loading.png", shot());
    release();
    await expect.soft(page.locator("#screen-trade")).toBeVisible({ timeout: 120_000 });
  });
});

test.describe("the venue, reference session", () => {
  test("desktop: chart, book, form, open orders", async ({ page }) => {
    await referenceSession(page);
    await snap(page, page, "venue-desktop.png", shot());
  });

  test("panels: chart and book tabs", async ({ page }) => {
    await referenceSession(page);
    const chart = page.locator(".p-chart"), book = page.locator(".p-book");
    await snap(page, chart, "panel-price-chart.png", shot());
    await page.click(".tabs[data-group=chart] button[data-tab=depth]");
    await sync(page);
    await snap(page, chart, "panel-depth-chart.png", shot());
    await snap(page, book, "panel-book-exact.png", shot());
    await page.selectOption("#book-group", "0.1");
    await sync(page);
    await snap(page, book, "panel-book-0.10.png", shot());
    await page.click(".tabs[data-group=book] button[data-tab=trades]");
    await snap(page, book, "panel-recent-trades.png", shot());
  });

  test("panels: bottom tabs", async ({ page }) => {
    await referenceSession(page);
    const bottom = page.locator(".p-bottom");
    for (const tab of ["open", "hist", "fills", "assets"]) {
      await page.click(`.tabs[data-group=bottom] button[data-tab=${tab}]`);
      await snap(page, bottom, `panel-bottom-${tab}.png`, shot());
    }
  });

  test("panels: order form in every mode", async ({ page }) => {
    await openMarket(page);
    await step(page, 300);
    const form = page.locator(".p-form");
    const modes = [
      ["buy-limit", "#side-buy", "limit", null],
      ["buy-market-rcc", "#side-buy", "market", null],
      ["buy-market-eur", "#side-buy", "market", "EUR"],
      ["sell-limit", "#side-sell", "limit", null],
      ["sell-market", "#side-sell", "market", null],
    ];
    for (const [name, side, kind, unit] of modes) {
      await page.click(side);
      await page.click(`.kinds button[data-kind="${kind}"]`);
      if (unit && (await page.textContent("#f-unit")) !== unit) await page.click("#f-unit");
      await page.fill("#f-qty", "");
      await snap(page, form, `form-${name}-empty.png`, shot());
    }
    // a filled-in limit buy: price from MID, amount from the 50 % button
    await page.click("#side-buy");
    await page.click('.kinds button[data-kind="limit"]');
    await quick(page, "mid");
    await page.click('.pct-ticks a[data-p="50"]');
    await snap(page, form, "form-buy-limit-filled.png", shot());
  });

  test("toasts", async ({ page }) => {
    await openMarket(page);
    await step(page, 300);
    await page.click("#side-sell");
    await page.click('.kinds button[data-kind="market"]');
    await page.fill("#f-qty", "99999");
    await page.click("#f-submit");                      // rejected: insufficient RCC
    await page.fill("#f-qty", "1");
    await page.click("#f-submit");                      // filled
    await sync(page);
    await expect.soft(page.locator(".toast")).toHaveCount(3); // + the "market open" toast
    await snap(page, page.locator("#toasts"), "toasts.png");
  });

  for (const [label, vp] of [["tablet", TABLET], ["phone", PHONE]]) {
    test(`${label} layout`, async ({ page }) => {
      await page.setViewportSize(vp);
      await referenceSession(page);
      await snap(page, page, `venue-${label}.png`, shot({ fullPage: true }));
    });
  }
});
