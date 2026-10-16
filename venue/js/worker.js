/* worker.js — runs the frozen engine (Pyodide) in a background loop.
 *
 * Messages in:  init{cfg} | play | pause | speed{tps} | order{...} | cancel{id}
 *               | cancelAll | view{group, depth}
 *               | stepN{k} | ping{id}            (test hooks, see app.js ?e2e)
 * Messages out: loading{msg} | ready{snap, config} | update{step, snap, depth}
 *               | result{...} | error{msg}
 *
 * A tick is one engine step. While playing, the loop runs the number of ticks
 * the dial asks for, in batches that keep the worker responsive. A message
 * (an order, a cancel) is only ever handled BETWEEN two batches, so human
 * orders always land between ticks. */

// the deploy's version stamp, from our own URL (app.js sets it)
const BUILD = new URL(self.location.href).searchParams.get("v") || "dev";
const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
// the frozen engine sits at the repo root, the wrapper next to the site
const PY_FILES = { "simulation_mvp.py": "../../simulation_mvp.py", "venue_wrapper.py": "../py/venue_wrapper.py" };

let py = null;          // the Pyodide instance
let api = null;         // python glue functions
let playing = false;
let tps = 10;           // ticks per second asked for
let acc = 0;            // fractional ticks owed
let lastT = 0;
let msPerTick = 1;      // running estimate of the engine's cost
let group = 0;
let wantDepth = false;
let timer = null;
let tickCount = 0, rateT0 = 0, rate = 0;

const post = (m) => self.postMessage(m);

const GLUE = `
import json, sys
sys.path.insert(0, "/venue")
from venue_wrapper import Venue
V = None

def _new(cfg):
    global V
    V = None
    V = Venue(**json.loads(cfg))
    return json.dumps(dict(snap=V.snapshot(), config=V.config()))

def _step(k, group, depth):
    r = V.step(int(k))
    return json.dumps(dict(step=r, snap=V.snapshot(group=float(group)),
                           depth=(V.depth() if depth else None)))

def _view(group, depth):
    return json.dumps(dict(snap=V.snapshot(group=float(group)),
                           depth=(V.depth() if depth else None)))

def _order(o):
    o = json.loads(o)
    r = V.place(o["side"], o["kind"], qty=o.get("qty"), price=o.get("price"),
                eur_amount=o.get("eur_amount"))
    return json.dumps(r)

def _cancel(i):
    return json.dumps(V.cancel(int(i)))

def _cancel_all():
    out = []
    for o in V.open_orders():
        out += V.cancel(o["id"])["orders"]
    return json.dumps(dict(orders=out))
`;

async function boot() {
  if (py) return;
  post({ type: "loading", msg: "Loading Python (WebAssembly)…" });
  importScripts(PYODIDE_URL + "pyodide.js");
  py = await loadPyodide({ indexURL: PYODIDE_URL });
  post({ type: "loading", msg: "Loading numpy…" });
  await py.loadPackage("numpy");
  post({ type: "loading", msg: "Loading the Alpha Engine…" });
  py.FS.mkdirTree("/venue");
  for (const [f, rel] of Object.entries(PY_FILES)) {
    const r = await fetch(new URL(`${rel}?v=${encodeURIComponent(BUILD)}`, self.location.href));
    if (!r.ok) throw new Error("could not fetch " + f);
    py.FS.writeFile("/venue/" + f, await r.text());
  }
  py.runPython(GLUE);
  const g = py.globals;
  api = {
    new: g.get("_new"), step: g.get("_step"), view: g.get("_view"),
    order: g.get("_order"), cancel: g.get("_cancel"), cancelAll: g.get("_cancel_all"),
  };
}

function schedule(delay) {
  clearTimeout(timer);
  timer = setTimeout(loop, delay);
}

function loop() {
  if (!playing || !api) return;
  const now = performance.now();
  acc += (now - lastT) / 1000 * tps;
  lastT = now;
  // cap one batch at ~40 ms of engine time so messages stay snappy
  const cap = Math.max(1, Math.floor(40 / Math.max(msPerTick, 0.05)));
  let k = Math.min(Math.floor(acc), cap);
  if (acc > cap * 3) acc = cap;          // can't keep up: drop the backlog, don't spiral
  if (k >= 1) {
    acc -= k;
    const t0 = performance.now();
    const out = JSON.parse(api.step(k, group, wantDepth));
    const dt = performance.now() - t0;
    msPerTick = 0.8 * msPerTick + 0.2 * (dt / k);
    tickCount += out.step.ticks.length;
    if (now - rateT0 > 1000) { rate = tickCount * 1000 / (now - rateT0); tickCount = 0; rateT0 = now; }
    out.rate = rate;
    post({ type: "update", ...out });
    if (!out.step.alive) { playing = false; post({ type: "stopped", reason: out.step.stopped }); return; }
  }
  // next frame: soon enough for the dial, never a busy spin
  const wait = Math.max(0, Math.min(1000 / Math.max(tps, 1), 33) - (performance.now() - now));
  schedule(k >= cap ? 0 : wait);
}

self.onmessage = async (ev) => {
  const m = ev.data;
  try {
    switch (m.type) {
      case "init": {
        playing = false;
        if (m.fixedNow != null) { const now = m.fixedNow; Date.now = () => now; }   // ?e2e only
        await boot();
        post({ type: "loading", msg: "Building the crowd…" });
        const out = JSON.parse(api.new(JSON.stringify(m.cfg)));
        post({ type: "ready", ...out });
        break;
      }
      case "play":
        if (!api) return;
        playing = true; lastT = performance.now(); acc = Math.max(acc, 1);
        rateT0 = lastT; tickCount = 0;
        schedule(0);
        break;
      case "stepN": {                    // test hook: exactly k ticks, paused
        if (!api || playing) return;
        const out = JSON.parse(api.step(m.k, group, wantDepth));
        post({ type: "update", ...out });
        break;
      }
      case "ping":                        // test hook: every earlier message is done
        post({ type: "pong", id: m.id });
        break;
      case "pause":
        playing = false; clearTimeout(timer); acc = 0; rate = 0;
        break;
      case "speed":
        tps = Math.max(0.1, +m.tps);
        break;
      case "view":
        group = +m.group || 0; wantDepth = !!m.depth;
        if (api) post({ type: "update", step: null, ...JSON.parse(api.view(group, wantDepth)) });
        break;
      case "order": {
        const r = JSON.parse(api.order(JSON.stringify(m.order)));
        post({ type: "result", kind: "order", ...r });
        post({ type: "update", step: null, ...JSON.parse(api.view(group, wantDepth)) });
        break;
      }
      case "cancel": {
        const r = JSON.parse(api.cancel(m.id));
        post({ type: "result", kind: "cancel", ...r });
        post({ type: "update", step: null, ...JSON.parse(api.view(group, wantDepth)) });
        break;
      }
      case "cancelAll": {
        const r = JSON.parse(api.cancelAll());
        post({ type: "result", kind: "cancel", ...r });
        post({ type: "update", step: null, ...JSON.parse(api.view(group, wantDepth)) });
        break;
      }
    }
  } catch (e) {
    let msg = String(e && e.message ? e.message : e);
    const lines = msg.trim().split("\n");
    post({ type: "error", msg: lines[lines.length - 1], detail: msg, during: m.type });
  }
};
