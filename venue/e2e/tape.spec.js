// The GUI against the engine: run n = 2 in the browser (Pyodide, through the
// venue wrapper, human idle with no coins) and compare the price chart's own
// tick tape with the bare engine's, run natively in CPython
// (venue/tests/reference_tape_n2.json, checked fresh by pytest).
const fs = require("fs");
const path = require("path");
const { test, expect, openMarket, step } = require("./fixtures");

const REF = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "tests", "reference_tape_n2.json"), "utf8"));

for (const c of REF.cases) {
  test(`n=2 ${c.arm}: ${c.T.toLocaleString("en-US")} ticks bit-identical to the engine`, async ({ page }) => {
    await openMarket(page, { arm: c.arm, n: c.n, seed: c.seed, K: REF.K, tp: REF.tp * 100, sl: REF.sl * 100,
      c: REF.c, q: REF.q, eur: 0, rcc: 0 });
    await step(page, c.T);
    const { hexes, sha, vol } = await page.evaluate(async () => {
      const tape = window.__rpm.tape();
      const dv = new DataView(new ArrayBuffer(8));
      const hexes = tape.map(([, p]) => {
        dv.setFloat64(0, p);                                   // big-endian, like struct ">d"
        return dv.getBigUint64(0).toString(16).padStart(16, "0");
      });
      const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(hexes.join("")));
      const sha = [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
      const vol = window.__rpm.volumes().reduce((a, b) => a + b, 0);
      return { hexes: hexes.filter((_, i) => i % 1000 === 0), sha, vol };
    });
    expect(hexes, "every 1000th tick (locates a divergence)").toEqual(c.every_1000);
    expect(sha, "whole tick tape, bit for bit").toBe(c.sha256);
    expect(Math.abs(vol - c.volume) / c.volume).toBeLessThan(1e-9);
  });
}
