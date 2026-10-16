// Downloads the exact Pyodide files the venue loads into ./pyodide-cache, so
// the tests never depend on a CDN mid-run. The tests serve this directory in
// place of cdn.jsdelivr.net (see fixtures.js).
const fs = require("fs");
const https = require("https");
const path = require("path");

const VERSION = "0.27.7";
const BASE = `https://cdn.jsdelivr.net/pyodide/v${VERSION}/full/`;
const FILES = [
  "pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip",
  "pyodide-lock.json", "numpy-2.0.2-cp312-cp312-pyodide_2024_0_wasm32.whl",
];
const DIR = path.join(__dirname, "pyodide-cache");

function get(url, dest) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location)
        return get(new URL(res.headers.location, url).toString(), dest).then(resolve, reject);
      if (res.statusCode !== 200) return reject(new Error(`${url}: HTTP ${res.statusCode}`));
      const out = fs.createWriteStream(dest);
      res.pipe(out);
      out.on("finish", () => out.close(resolve));
    }).on("error", reject);
  });
}

(async () => {
  fs.mkdirSync(DIR, { recursive: true });
  for (const f of FILES) {
    const dest = path.join(DIR, f);
    if (fs.existsSync(dest) && fs.statSync(dest).size > 0) continue;
    process.stdout.write(`fetching ${f} … `);
    await get(BASE + f, dest);
    console.log(fs.statSync(dest).size, "bytes");
  }
})().catch((e) => { console.error(e); process.exit(1); });
