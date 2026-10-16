// Minimal static server for the repo root (the page loads ../simulation_mvp.py).
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..", "..");
const PORT = +process.env.PORT || 8123;
const TYPES = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".py": "text/x-python", ".json": "application/json", ".svg": "image/svg+xml" };

http.createServer((req, res) => {
  const url = decodeURIComponent(req.url.split("?")[0]);
  let p = path.normalize(path.join(ROOT, url));
  if (!p.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p = path.join(p, "index.html");
  fs.readFile(p, (err, body) => {
    if (err) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "content-type": TYPES[path.extname(p)] || "application/octet-stream" });
    res.end(body);
  });
}).listen(PORT, "127.0.0.1", () => console.log(`serving ${ROOT} on :${PORT}`));
