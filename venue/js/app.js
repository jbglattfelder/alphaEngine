/* app.js — the venue's screens. All market logic lives in the worker. */
(() => {
  "use strict";

  // the deploy's version stamp (see index.html), handed to every file loaded later
  const BUILD = new URL(document.currentScript.src).searchParams.get("v") || "dev";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const X0 = 100, MAX_FRAC = 0.75;

  // ── formatting ────────────────────────────────────────────────────────
  const nf = (d) => new Intl.NumberFormat(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const F2 = nf(2), F4 = nf(4), F0 = nf(0);
  const px = (v) => (v == null || !isFinite(v) ? "—" : F2.format(v));
  const qty = (v) => (v == null || !isFinite(v) ? "—" : F4.format(v));
  const eur = (v) => (v == null || !isFinite(v) ? "—" : F2.format(v) + " EUR");
  const signed = (v, unit = " EUR") => (v == null || !isFinite(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + F2.format(Math.abs(v)) + unit);
  const cls = (v) => (v > 1e-9 ? "up" : v < -1e-9 ? "dn" : "");
  const hms = (ms) => new Date(ms).toLocaleTimeString([], { hour12: false });
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  function toast(msg, kind = "") {
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.textContent = msg;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), 4200);
    while ($("#toasts").children.length > 4) $("#toasts").firstChild.remove();
  }
  function show(id) {
    $$(".screen, #screen-trade").forEach((s) => s.classList.add("hidden"));
    $(id).classList.remove("hidden");
  }

  // ═════════════ state ═════════════
  const S = {
    name: "", cfg: null, playing: false, tps: 10, group: 0,
    snap: null, side: "buy", kind: "limit", unit: "RCC",
    orders: new Map(), fills: [], tape: [], lastPrice: X0,
    chartTab: "price", markers: [], priceLines: new Map(), chartData: 0,
  };

  // ═════════════ 1. sign in ═════════════
  // A gate, not security: the site is static, so the check runs in the page.
  // Only the SHA-256 of "user:password" is shipped, not the password itself.
  const LOGIN_SHA256 = "416b8774416750341da8e44b95de13ab24add867e576ec904409919b9dfefff5";
  async function sha256hex(text) {
    const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  $("#btn-login").onclick = async () => {
    const user = $("#login-name").value.trim(), pass = $("#login-pass").value;
    if ((await sha256hex(`${user}:${pass}`)) !== LOGIN_SHA256) {
      $("#login-err").textContent = "Wrong username or password";
      return;
    }
    $("#login-err").textContent = "";
    S.name = user;
    $("#avatar").textContent = S.name[0].toUpperCase();
    $("#avatar").title = S.name;
    show("#screen-config");
    updateAlloc();
  };
  $$("#screen-login input").forEach((i) => i.addEventListener("input", () => ($("#login-err").textContent = "")));
  $$("#screen-login input").forEach((i) => i.addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btn-login").click(); }));

  // ═════════════ 2. configure ═════════════
  let arm = "NNNN";
  $$("#cfg-arm button").forEach((b) => (b.onclick = () => {
    arm = b.dataset.v;
    $$("#cfg-arm button").forEach((x) => x.classList.toggle("on", x === b));
    $("#cfg-band-note").textContent = arm === "NNNN" ? "mean of per-agent draws, cv 0.3" : "identical for every agent";
  }));
  ["#cfg-K", "#cfg-eur", "#cfg-rcc"].forEach((s) => $(s).addEventListener("input", updateAlloc));
  $$("#screen-config input").forEach((i) => i.addEventListener("input", () => ($("#cfg-err").textContent = "")));

  function readCfg() {
    const v = (s) => parseFloat($(s).value);
    return {
      n: Math.round(v("#cfg-n")), K: v("#cfg-K"), tp: v("#cfg-tp") / 100, sl: v("#cfg-sl") / 100,
      c: v("#cfg-c"), q: Math.round(v("#cfg-q")), seed: Math.round(v("#cfg-seed")), arm,
      user_eur: v("#cfg-eur") || 0, user_rcc: v("#cfg-rcc") || 0,
    };
  }
  function updateAlloc() {
    const c = readCfg();
    const val = c.user_eur + c.user_rcc * X0, max = MAX_FRAC * (c.K || 0);
    const f = max > 0 ? val / max : 0;
    $("#alloc-fill").style.width = Math.min(100, f * 100) + "%";
    $("#alloc-fill").classList.toggle("over", f > 1 + 1e-12);
    $("#alloc-val").textContent = `Your value at x₀: ${F0.format(val)} EUR (${F0.format(c.user_eur)} EUR + ${F4.format(c.user_rcc)} RCC)`;
    $("#alloc-max").textContent = `max ${F0.format(max)} EUR`;
  }
  function validate(c) {
    if (!(c.n >= 1 && c.n <= 10000)) return "n must be between 1 and 10,000 agents per side";
    if (!(c.K > 0)) return "K must be positive";
    if (!(c.tp > 0 && c.sl > 0)) return "take profit and stop loss must be positive";
    if (!(c.c > 0)) return "c must be positive";
    if (!(c.q >= 1)) return "q must be at least 1";
    if (!(c.seed >= 0)) return "seed must be a non-negative integer";
    if (c.user_eur < 0 || c.user_rcc < 0) return "allocation must be non-negative";
    if (c.user_eur + c.user_rcc * X0 > MAX_FRAC * c.K * (1 + 1e-12)) return "your allocation exceeds 75% of K";
    return "";
  }
  $("#btn-launch").onclick = () => {
    const c = readCfg();
    const err = validate(c);
    $("#cfg-err").textContent = err;
    if (err) return;
    S.cfg = c;
    show("#screen-loading");
    // ?e2e: the worker's clock is frozen to the page's (tests freeze both)
    worker.postMessage({ type: "init", cfg: c, fixedNow: params.has("e2e") ? Date.now() : null });
  };

  // ═════════════ worker ═════════════
  const worker = new Worker(`js/worker.js?v=${encodeURIComponent(BUILD)}`);
  const pongs = new Map();

  // Test hooks for venue/e2e, only with ?e2e in the URL. step(k) runs exactly
  // k ticks while paused; sync() resolves once the worker has handled every
  // earlier message and the page has rendered its replies.
  const params = new URLSearchParams(location.search);
  // a market starts playing on open; under ?e2e only with &autoplay (tests step it)
  const AUTOPLAY = !params.has("e2e") || params.has("autoplay");
  if (params.has("e2e")) {
    let pid = 0;
    const sync = () => new Promise((r) => { const id = ++pid; pongs.set(id, r); worker.postMessage({ type: "ping", id }); });
    window.__rpm = {
      sync,
      step: (k) => { worker.postMessage({ type: "stepN", k }); return sync(); },
      tape: () => series.data().map((d) => [d.time, d.value]),        // the chart's tick tape
      volumes: () => volume.data().map((d) => d.value),
      markers: () => S.markers.length,
      visible: () => chart.timeScale().getVisibleLogicalRange(),
      position: () => S.position && S.position.side ? S.position : null,
      orderLines: () => [...S.priceLines.values()].map((pl) => pl.options()),
    };
  }
  worker.onmessage = (ev) => {
    const m = ev.data;
    if (m.type === "loading") $("#loading-msg").textContent = m.msg;
    else if (m.type === "ready") onReady(m);
    else if (m.type === "update") onUpdate(m);
    else if (m.type === "result") onResult(m);
    else if (m.type === "pong") { const r = pongs.get(m.id); pongs.delete(m.id); if (r) r(); }
    else if (m.type === "stopped") { setPlaying(false); banner("Market stopped: " + m.reason); }
    else if (m.type === "error") {
      console.error(m.detail || m.msg);
      if (m.during === "init") { show("#screen-config"); $("#cfg-err").textContent = m.msg; }
      else toast(m.msg, "bad");
      $("#f-submit").disabled = false;
    }
  };

  // ═════════════ 3. the venue ═════════════
  let chart, series, volume;
  function onReady(m) {
    resetVenue();
    show("#screen-trade");
    $("#hdr-arm").textContent = m.config.arm;
    initChart();
    onUpdate({ step: null, snap: m.snap });
    S.lastPrice = m.snap.market.price;
    series.setData([{ time: 0, value: m.snap.market.price }]);
    volume.setData([{ time: 0, value: 0, color: VOL_UP }]);
    S.chartData = 1;
    S.prevPrice = m.snap.market.price;
    setPlaying(false);
    worker.postMessage({ type: "speed", tps: S.tps });
    pushView();
    toast(`Market open · ${2 * m.config.n} agents · ${m.config.arm} · seed ${m.config.seed}.${AUTOPLAY ? "" : " Press play."}`, "ok");
    if (AUTOPLAY) { setPlaying(true); worker.postMessage({ type: "play" }); }
  }
  function resetVenue() {
    S.orders.clear(); S.fills = []; S.tape = []; S.markers = [];
    S.openHtml = null; S.posKey = null; S.position = null;
    S.priceLines.clear();
    $("#banner").classList.add("hidden");
    $("#tape").innerHTML = "";
    if (chart) { chart.remove(); chart = null; }
  }

  function initChart() {
    chart = LightweightCharts.createChart($("#chart"), {
      autoSize: true,
      layout: { background: { color: "#141519" }, textColor: "#8a919e", fontFamily: getComputedStyle(document.body).fontFamily },
      grid: { vertLines: { color: "#1d2026" }, horzLines: { color: "#1d2026" } },
      rightPriceScale: { borderColor: "#262a31", scaleMargins: { top: 0.08, bottom: 0.24 } },
      // minBarSpacing: zoom out until the whole session fits (default 0.5 px per tick)
      timeScale: { borderColor: "#262a31", tickMarkFormatter: (t) => "t " + F0.format(t), rightOffset: 6, minBarSpacing: 0.001 },
      localization: { timeFormatter: (t) => "tick " + F0.format(t), priceFormatter: (p) => F2.format(p) },
      crosshair: { mode: 0 },
    });
    series = chart.addLineSeries({ color: "#3773f5", lineWidth: 2, priceLineColor: "#3773f5", lastValueVisible: true });
    // volume per tick (RCC), on its own scale in the bottom fifth
    volume = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" },
      lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
  }
  const VOL_UP = "rgba(39, 173, 117, 0.45)", VOL_DN = "rgba(240, 97, 109, 0.45)";

  function onUpdate(m) {
    const st = m.step;
    if (st) {
      if (st.ticks.length) {
        for (const [t, p, v] of st.ticks) {
          series.update({ time: t, value: p });
          volume.update({ time: t, value: v, color: p >= S.prevPrice ? VOL_UP : VOL_DN });
          S.prevPrice = p;
        }
        S.chartData += st.ticks.length;
        if (S.chartData > 300000) trimChart();
      }
      if (st.prints.length) addPrints(st.prints);
      if (m.rate != null) $("#speed-real").textContent = S.playing ? `(running ${F0.format(m.rate)})` : "";
    }
    if (st) { onFills(st.fills); onOrders(st.orders); }
    if (m.snap) render(m.snap);
    if (m.depth && S.chartTab === "depth") drawDepth(m.depth);
  }
  function trimChart() {
    // keep the most recent 150k ticks on screen
    const data = series.data().slice(-150000);
    series.setData(data);
    volume.setData(volume.data().slice(-150000));
    S.chartData = data.length;
  }

  function onResult(m) {
    $("#f-submit").disabled = false;
    if (m.prints && m.prints.length) addPrints(m.prints);
    onFills(m.fills || []);
    onOrders(m.orders || []);
    if (m.kind === "order") {
      const o = m.order;
      const what = `${o.side === "buy" ? "Buy" : "Sell"} ${o.kind}`;
      if (o.status === "rejected") toast(`${what} rejected: ${o.reason}`, "bad");
      else if (o.status === "filled") toast(`${what} filled: ${qty(o.filled)} RCC @ ${px(o.avg)}`, "ok");
      else if (o.status === "cancelled") toast(o.filled > 0 ? `${what}: ${qty(o.filled)} RCC @ ${px(o.avg)}, ${o.reason}` : `${what}: ${o.reason}`, o.filled > 0 ? "" : "bad");
      else toast(`${what} placed${o.filled > 0 ? `, ${qty(o.filled)} filled now` : ""}: ${qty(o.remaining)} RCC resting @ ${px(o.price)}`, "ok");
      if (o.status !== "rejected") { $("#f-qty").value = ""; $("#f-pct").value = 0; }
    }
  }

  function onOrders(list) {
    for (const o of list) {
      const prev = S.orders.get(o.id);
      S.orders.set(o.id, o);
      if (prev && prev.status !== o.status && (o.status === "filled") && o.kind === "limit" && prev.status !== "filled")
        toast(`Limit ${o.side} #${o.id} filled: ${qty(o.filled)} RCC @ ${px(o.avg)}`, "ok");
    }
    if (list.length) renderHistory();
  }
  function onFills(list) {
    if (!list.length) return;
    for (const f of list) {
      S.fills.unshift(f);
      // one arrow per order and tick: a market order that sweeps several
      // makers is one trade decision, not a column of arrows
      const key = `${f.tick}:${f.side}:${f.order}`;
      if (S.markers.some((k) => k.key === key)) continue;
      S.markers.push({ key, time: f.tick, position: f.side === "buy" ? "belowBar" : "aboveBar",
        color: f.side === "buy" ? "#27ad75" : "#f0616d", shape: f.side === "buy" ? "arrowUp" : "arrowDown", text: "" });
    }
    if (S.fills.length > 2000) S.fills.length = 2000;
    // markers must be sorted and on existing points
    const last = series.data().length ? series.data().at(-1).time : 0;
    S.markers = S.markers.filter((k) => k.time <= last).slice(-300).sort((a, b) => a.time - b.time);
    series.setMarkers(S.markers);
    renderFills();
  }

  function addPrints(prints) {
    const now = Date.now();
    for (const p of prints) S.tape.unshift({ t: p[0], id: p[1], price: p[2], size: p[3], side: p[4], me: p[5], wall: now });
    if (S.tape.length > 80) S.tape.length = 80;
    $("#tape").innerHTML = S.tape.map((r) =>
      `<div class="bk-row ${r.side}${r.me ? " me" : ""}" title="tick ${r.t} · print #${r.id}"><span>${px(r.price)}</span><span>${qty(r.size)}</span><span>${hms(r.wall)}</span></div>`).join("");
  }

  // ── render a snapshot ────────────────────────────────────────────────
  function render(s) {
    S.snap = s;
    const mk = s.market, a = s.account, pnl = a.pnl;
    S.lastPrice = mk.price;
    const chg = mk.price / X0 - 1;
    $("#hdr-last").textContent = px(mk.price);
    $("#hdr-chg").textContent = (chg >= 0 ? "+" : "−") + F2.format(Math.abs(chg * 100)) + "%";
    $("#hdr-chg").className = chg >= 0 ? "up" : "dn";
    $("#hdr-hl").textContent = `${px(mk.hi)} / ${px(mk.lo)}`;
    $("#hdr-vol").textContent = F2.format(mk.volume);
    $("#hdr-alive").textContent = `${mk.alive} / ${mk.population}`;
    $("#hdr-tick").textContent = F0.format(mk.t);
    $("#bk-last").textContent = px(mk.price);
    $("#bk-last").className = "";
    renderBook(s.book);

    $("#a-eur").textContent = F2.format(a.eur);
    $("#a-rcc").textContent = F4.format(a.rcc);
    $("#a-wealth").textContent = F2.format(pnl.wealth);
    setPnl("#a-real", pnl.realised); setPnl("#a-unreal", pnl.unrealised); setPnl("#a-total", pnl.total);
    renderAvail();
    renderOpen(s.open_orders);
    renderAssets(a, mk.price);
    renderPosition(pnl);
    syncPriceLines(s.open_orders);
  }
  function setPnl(sel, v) { const el = $(sel); el.textContent = signed(v); el.className = cls(v); }

  function renderBook(b) {
    const rows = (lv, side) => {
      let cum = 0;
      return lv.map(([p, s, mine]) => { cum += s; return { p, s, cum, mine }; });
    };
    const asks = rows(b.asks, "ask"), bids = rows(b.bids, "bid");
    const maxCum = Math.max(asks.length ? asks.at(-1).cum : 0, bids.length ? bids.at(-1).cum : 0, 1e-12);
    const row = (r) => `<div class="bk-row${r.mine > 0 ? " mine" : ""}" data-p="${r.p}"><i style="width:${(100 * r.cum / maxCum).toFixed(1)}%"></i><span>${px(r.p)}</span><span>${qty(r.s)}</span><span>${qty(r.cum)}</span></div>`;
    $("#asks").innerHTML = asks.length ? asks.slice().reverse().map(row).join("") : `<div class="bk-empty">no asks</div>`;
    $("#bids").innerHTML = bids.length ? bids.map(row).join("") : `<div class="bk-empty">no bids</div>`;
    if (b.best_bid != null && b.best_ask != null) {
      const sp = b.best_ask - b.best_bid, mid = (b.best_ask + b.best_bid) / 2;
      $("#bk-spread").textContent = `Spread ${F4.format(sp)} (${F2.format(sp / mid * 1e4)} bps)`;
    } else $("#bk-spread").textContent = b.best_bid == null && b.best_ask == null ? "Book empty" : (b.best_bid == null ? "No bids" : "No asks");
  }
  // on press, not click: the book is redrawn every tick, so the row under the
  // pointer at release is usually a new element and a click would not fire
  $("#screen-trade").addEventListener("pointerdown", (e) => {
    const r = e.target.closest(".bk-side .bk-row");
    if (r && e.button === 0) { setKind("limit"); $("#f-price").value = (+r.dataset.p).toFixed(2); updateTotal(); }
  });

  function renderOpen(list) {
    $("#cnt-open").textContent = list.length;
    $("#e-open").classList.toggle("hidden", list.length > 0);
    // redraw only when a row changed: replacing the table on every update (up to
    // ~30/s while playing) swaps the Cancel button out between press and release,
    // and the browser then drops the click
    const html = list.slice().reverse().map((o) => `<tr>
      <td>${hms(o.wall * 1000)}</td><td class="num">${o.tick}</td>
      <td class="${o.side === "buy" ? "up" : "dn"}">${o.side.toUpperCase()}</td><td>${o.kind}</td>
      <td class="num">${px(o.price)}</td><td class="num">${qty(o.qty)}</td><td class="num">${qty(o.filled)}</td>
      <td class="num">${qty(o.remaining)}</td><td><span class="st ${o.status}">${o.status}</span></td>
      <td><button class="x" data-cancel="${o.id}">Cancel</button></td></tr>`).join("");
    if (html !== S.openHtml) { $("#t-open").innerHTML = html; S.openHtml = html; }
  }
  $("#t-open").addEventListener("click", (e) => {
    const b = e.target.closest("[data-cancel]");
    if (b) worker.postMessage({ type: "cancel", id: +b.dataset.cancel });
  });
  $("#btn-cancel-all").onclick = () => worker.postMessage({ type: "cancelAll" });

  // ── position: one pair, so at most one. Long = net RCC bought, short = net
  // RCC sold (EUR bought). The row is built when the position opens or flips;
  // after that only its numbers change, so its buttons stay clickable.
  function renderPosition(P) {
    S.position = P;
    $("#cnt-pos").textContent = P.side ? 1 : 0;
    $("#e-pos").classList.toggle("hidden", !!P.side);
    const tb = $("#t-pos");
    if (!P.side) { if (tb.firstChild) tb.innerHTML = ""; S.posKey = null; return; }
    const key = `${P.side}:${P.opened_tick}`;
    if (key !== S.posKey) {
      const inc = P.side === "long" ? "buy" : "sell", dec = P.side === "long" ? "sell" : "buy";
      tb.innerHTML = `<tr>
        <td><b>RCC-EUR</b></td>
        <td class="${P.side === "long" ? "up" : "dn"}">${P.side === "long" ? "LONG" : "SHORT"}</td>
        <td class="num" data-f="size"></td><td class="num" data-f="value"></td>
        <td class="num" data-f="entry"></td><td class="num" data-f="avg"></td><td class="num" data-f="mark"></td>
        <td class="num" data-f="upnl"></td><td class="num" data-f="opened"></td>
        <td class="acts"><button class="x" data-pos="close">Close</button><button class="x" data-pos="${inc}" title="${inc} more at market">Increase</button><button class="x" data-pos="${dec}" title="${dec} part at market">Decrease</button></td></tr>`;
      S.posKey = key;
    }
    const f = (k, v) => { const el = tb.querySelector(`[data-f="${k}"]`); if (el.textContent !== v) el.textContent = v; };
    f("size", qty(P.size)); f("value", F2.format(P.value)); f("entry", px(P.entry_price));
    f("avg", px(P.avg_price)); f("mark", px(P.x_prime)); f("upnl", signed(P.unrealised));
    f("opened", P.opened_tick == null ? "—" : "t " + F0.format(P.opened_tick));
    tb.querySelector('[data-f="upnl"]').className = "num " + cls(P.unrealised);
  }
  $("#t-pos").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pos]");
    const P = S.position;
    if (!b || !P || !P.side) return;
    const what = b.dataset.pos;
    if (what === "close") {
      // close = the whole position at market: sell a long, buy back a short
      $("#f-submit").disabled = true;
      worker.postMessage({ type: "order", order: { side: P.side === "long" ? "sell" : "buy", kind: "market", qty: P.size } });
      return;
    }
    // increase / decrease: set up the order form, the amount is yours to choose
    setSide(what); setKind("market");
    if (S.unit !== "RCC") { S.unit = "RCC"; refreshForm(); }
    $("#f-qty").value = ""; $("#f-pct").value = 0; updateTotal();
    $("#f-qty").focus();
  });

  function renderHistory() {
    const list = [...S.orders.values()].filter((o) => !["open", "partial"].includes(o.status)).sort((a, b) => b.id - a.id).slice(0, 500);
    $("#e-hist").classList.toggle("hidden", list.length > 0);
    $("#t-hist").innerHTML = list.map((o) => `<tr>
      <td>${hms(o.wall * 1000)}</td><td class="num">${o.tick}</td>
      <td class="${o.side === "buy" ? "up" : "dn"}">${o.side.toUpperCase()}</td><td>${o.kind}</td>
      <td class="num">${o.kind === "market" ? "market" : px(o.price)}</td>
      <td class="num">${o.qty != null ? qty(o.qty) + " RCC" : eur(o.eur_amount)}</td>
      <td class="num">${qty(o.filled)}</td><td class="num">${px(o.avg)}</td>
      <td><span class="st ${o.status}">${o.status}</span></td><td class="muted">${esc(o.reason || "")}</td></tr>`).join("");
  }
  function renderFills() {
    $("#e-fills").classList.toggle("hidden", S.fills.length > 0);
    $("#t-fills").innerHTML = S.fills.slice(0, 500).map((f) => `<tr>
      <td>${hms(f.wall * 1000)}</td><td class="num">${f.tick}</td>
      <td class="${f.side === "buy" ? "up" : "dn"}">${f.side.toUpperCase()}</td>
      <td class="num">${px(f.price)}</td><td class="num">${qty(f.size)}</td><td class="num">${F2.format(f.size * f.price)}</td>
      <td>${f.role}</td><td class="muted">${esc(f.counterparty)}</td>
      <td class="num ${cls(f.realised)}">${f.realised ? signed(f.realised, "") : "—"}</td></tr>`).join("");
  }
  function renderAssets(a, p) {
    $("#t-assets").innerHTML = `
      <tr><td><b>EUR</b></td><td class="num">${F2.format(a.eur)}</td><td class="num">${F2.format(a.avail_eur)}</td><td class="num">${F2.format(a.locked_eur)}</td><td class="num">${F2.format(a.Q)}</td><td class="num">${F2.format(a.eur)}</td></tr>
      <tr><td><b>RCC</b></td><td class="num">${F4.format(a.rcc)}</td><td class="num">${F4.format(a.avail_rcc)}</td><td class="num">${F4.format(a.locked_rcc)}</td><td class="num">${F4.format(a.B)}</td><td class="num">${F2.format(a.rcc * p)}</td></tr>`;
    const P = a.pnl;
    const cell = (label, val, note, c = "") => `<div><small>${label}</small><b class="${c}">${val}</b><em>${note}</em></div>`;
    $("#pnlgrid").innerHTML = [
      cell("Realised PnL", signed(P.realised), "banked q of closed round trips", cls(P.realised)),
      cell("Unrealised PnL", signed(P.unrealised), "x′·b + q of the open position", cls(P.unrealised)),
      cell("Total PnL p<sup>q</sup>", signed(P.total), "Eq. 9b: x′·b + q vs not trading", cls(P.total)),
      cell("Total PnL p<sup>b</sup>", signed(P.total_rcc, " RCC"), "Eq. 3 / 9a: b + q/x′", cls(P.total_rcc)),
      cell("Mark x′", px(P.x_prime), P.position > 0 ? "best bid (long closes there)" : P.position < 0 ? "best ask (short closes there)" : "flat: ask if q > 0, bid if q < 0"),
      cell("Position b", qty(P.position) + " RCC", "Eq. 1a: net RCC bought"),
      cell("Average price x̄", px(P.avg_price), "Eq. 2: −q/b"),
      cell("Wealth W<sup>q</sup>", F2.format(P.wealth) + " EUR", "Eq. 8b: x′(B+b) + Q + q"),
      cell("Wealth W<sup>b</sup>", qty(P.wealth_rcc) + " RCC", "Eq. 8a: W<sup>q</sup>/x′"),
      cell("Performance p̃", (P.perf >= 0 ? "+" : "−") + F4.format(Math.abs(P.perf * 100)) + " %", "Sec. 3: p<sup>b</sup> / (B + Q/x₀)", cls(P.perf)),
      cell("Volume", qty(P.volume) + " RCC", `${P.n_fills} fills · no fees`),
    ].join("");
  }

  function syncPriceLines(open) {
    if (!series) return;
    const ids = new Set(open.map((o) => o.id));
    for (const [id, pl] of S.priceLines) if (!ids.has(id)) { series.removePriceLine(pl); S.priceLines.delete(id); }
    // a dotted line per open order, nothing on the price axis: several orders a
    // few cents apart must not stack label boxes over the chart (details live in
    // the Open orders tab)
    for (const o of open) if (!S.priceLines.has(o.id)) {
      S.priceLines.set(o.id, series.createPriceLine({ price: o.price, color: o.side === "buy" ? "#27ad75" : "#f0616d",
        lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: false, title: "" }));
    }
  }

  // ── depth chart ──────────────────────────────────────────────────────
  function drawDepth(d) {
    const cv = $("#depth"), dpr = window.devicePixelRatio || 1;
    const W = cv.clientWidth, H = cv.clientHeight;
    if (!W || !H) return;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext("2d");
    g.scale(dpr, dpr);
    g.fillStyle = "#141519"; g.fillRect(0, 0, W, H);
    const all = [...d.bids, ...d.asks];
    const p = S.lastPrice;
    const lo = p * 0.95, hi = p * 1.05;
    const maxQ = Math.max(1e-9, ...all.map((x) => x[1]));
    const X = (v) => 50 + (W - 70) * (v - lo) / (hi - lo), Y = (q) => H - 28 - (H - 50) * q / maxQ;
    const area = (pts, col, fill, dir) => {
      if (!pts.length) return;
      g.beginPath(); g.moveTo(X(pts[0][0]), Y(0));
      let prev = 0;
      for (const [x, q] of pts) { g.lineTo(X(x), Y(prev)); g.lineTo(X(x), Y(q)); prev = q; }
      g.lineTo(X(dir < 0 ? lo : hi), Y(prev)); g.lineTo(X(dir < 0 ? lo : hi), Y(0)); g.closePath();
      g.fillStyle = fill; g.fill(); g.strokeStyle = col; g.lineWidth = 1.5; g.stroke();
    };
    area(d.bids, "#27ad75", "rgba(39,173,117,.18)", -1);
    area(d.asks, "#f0616d", "rgba(240,97,109,.18)", +1);
    g.strokeStyle = "#3773f5"; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(X(p), 10); g.lineTo(X(p), H - 28); g.stroke(); g.setLineDash([]);
    g.fillStyle = "#8a919e"; g.font = "11px " + getComputedStyle(document.body).fontFamily;
    for (let i = 0; i <= 4; i++) { const v = lo + (hi - lo) * i / 4; g.fillText(F2.format(v), X(v) - 16, H - 10); }
    for (let i = 1; i <= 4; i++) { const q = maxQ * i / 4; g.fillText(F2.format(q), 4, Y(q) + 4); }
    g.fillText("cumulative RCC within ±5% of last", 56, 18);
  }

  // ── tabs ─────────────────────────────────────────────────────────────
  $$(".tabs[data-group]").forEach((bar) => bar.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-tab]");
    if (!b) return;
    $$("button[data-tab]", bar).forEach((x) => x.classList.toggle("on", x === b));
    const panel = bar.parentElement;
    $$(".tabpane", panel).forEach((p) => p.classList.toggle("on", p.dataset.pane === b.dataset.tab));
    if (bar.dataset.group === "chart") {
      S.chartTab = b.dataset.tab;
      $("#chart-note").classList.toggle("hidden", S.chartTab !== "price");
      // leaving the price chart resets its zoom, scroll and price axis, so
      // coming back always shows the live end of the curve
      if (S.chartTab !== "price" && chart) {
        chart.timeScale().resetTimeScale();
        chart.priceScale("right").applyOptions({ autoScale: true });
      }
      pushView();
    }
  }));
  $("#book-group").onchange = (e) => { S.group = +e.target.value; pushView(); };
  function pushView() { worker.postMessage({ type: "view", group: S.group, depth: S.chartTab === "depth" }); }
  new ResizeObserver(() => { if (S.chartTab === "depth") pushView(); }).observe($("#depth"));

  // ── transport ────────────────────────────────────────────────────────
  const speedFromDial = (v) => { const t = Math.pow(500, v / 100); return t < 10 ? Math.round(t * 10) / 10 : Math.round(t); };
  function setPlaying(on) {
    S.playing = on;
    $("#play-icon").setAttribute("d", on ? "M7 5h4v14H7zM13 5h4v14h-4z" : "M8 5v14l11-7z");
    if (!on) $("#speed-real").textContent = "";
  }
  $("#btn-play").onclick = () => { setPlaying(!S.playing); worker.postMessage({ type: S.playing ? "play" : "pause" }); };
  $("#speed").addEventListener("input", (e) => {
    S.tps = speedFromDial(+e.target.value);
    $("#speed-val").textContent = S.tps;
    worker.postMessage({ type: "speed", tps: S.tps });
  });
  $("#speed").value = 29; S.tps = 6; $("#speed-val").textContent = S.tps;     // start at 6 ticks/s
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !$("#screen-trade").classList.contains("hidden") && !/INPUT|SELECT|TEXTAREA|BUTTON/.test(document.activeElement.tagName)) {
      e.preventDefault(); $("#btn-play").click();
    }
  });
  $("#btn-new").onclick = () => {
    if (!confirm("Close this market? Its history and your orders are discarded.")) return;
    worker.postMessage({ type: "pause" }); setPlaying(false);
    show("#screen-config");
  };
  function banner(msg) { $("#banner").textContent = msg; $("#banner").classList.remove("hidden"); }

  // clock: the user's local time
  const tickClock = () => {
    const d = new Date();
    $("#hdr-time").textContent = d.toLocaleTimeString([], { hour12: false });
    $("#hdr-date").textContent = d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
  };
  tickClock(); setInterval(tickClock, 1000);

  // ═════════════ order form ═════════════
  function setSide(s) {
    S.side = s;
    $("#side-buy").classList.toggle("on", s === "buy");
    $("#side-sell").classList.toggle("on", s === "sell");
    $("#f-submit").className = "btn wide " + s;
    if (s === "sell") S.unit = "RCC";
    refreshForm();
  }
  function setKind(k) {
    S.kind = k;
    $$(".kinds button").forEach((b) => b.classList.toggle("on", b.dataset.kind === k));
    $("#f-price-row").classList.toggle("hidden", k === "market");
    if (k === "limit") S.unit = "RCC";
    refreshForm();
  }
  function refreshForm() {
    $("#f-unit").textContent = S.unit;
    $("#f-unit").disabled = !(S.side === "buy" && S.kind === "market");
    $("#f-submit").textContent = `${S.side === "buy" ? "Buy" : "Sell"} RCC${S.kind === "market" ? " at market" : ""}`;
    renderAvail(); updateTotal();
  }
  $("#side-buy").onclick = () => setSide("buy");
  $("#side-sell").onclick = () => setSide("sell");
  $$(".kinds button").forEach((b) => (b.onclick = () => setKind(b.dataset.kind)));
  $("#f-unit").onclick = () => { S.unit = S.unit === "RCC" ? "EUR" : "RCC"; $("#f-qty").value = ""; refreshForm(); };

  function renderAvail() {
    if (!S.snap) return;
    const a = S.snap.account;
    $("#f-avail").textContent = S.side === "buy" ? F2.format(a.avail_eur) + " EUR" : F4.format(a.avail_rcc) + " RCC";
  }
  function refPrice() {
    const b = S.snap && S.snap.book;
    if (S.kind === "limit") return parseFloat($("#f-price").value);
    if (!b) return S.lastPrice;
    return (S.side === "buy" ? b.best_ask : b.best_bid) ?? S.lastPrice;
  }
  function updateTotal() {
    const q = parseFloat($("#f-qty").value), p = refPrice();
    let txt = "—";
    if (q > 0) {
      if (S.unit === "EUR") txt = `≈ ${qty(q / p)} RCC`;
      else if (p > 0) txt = `${S.kind === "market" ? "≈ " : ""}${F2.format(q * p)} EUR`;
    }
    $("#f-total-lbl").textContent = S.kind === "market" ? "Estimated total" : "Total";
    $("#f-total").textContent = txt;
  }
  ["#f-qty", "#f-price"].forEach((s) => $(s).addEventListener("input", updateTotal));
  $$(".quick a").forEach((a) => (a.onclick = () => {
    const b = S.snap && S.snap.book;
    if (!b) return;
    const v = { bid: b.best_bid, ask: b.best_ask, mid: b.best_bid != null && b.best_ask != null ? (b.best_bid + b.best_ask) / 2 : S.lastPrice }[a.dataset.q] ?? S.lastPrice;
    $("#f-price").value = v.toFixed(2); updateTotal();
  }));
  function setPct(pct) {
    if (!S.snap) return;
    const a = S.snap.account, f = pct / 100;
    let v;
    if (S.side === "sell") v = a.avail_rcc * f;
    else if (S.unit === "EUR") v = a.avail_eur * f;
    else { const p = refPrice(); v = p > 0 ? a.avail_eur * f / p : 0; }
    // round down so "Max" never asks for more than is there
    const d = S.unit === "EUR" ? 100 : 1e4;
    $("#f-qty").value = (Math.floor(v * d * (1 - 1e-12)) / d).toString();
    $("#f-pct").value = pct; updateTotal();
  }
  $("#f-pct").addEventListener("input", (e) => setPct(+e.target.value));
  $$(".pct-ticks a").forEach((a) => (a.onclick = () => setPct(+a.dataset.p)));

  $("#f-submit").onclick = () => {
    const q = parseFloat($("#f-qty").value);
    if (!(q > 0)) return toast("Enter an amount", "bad");
    const o = { side: S.side, kind: S.kind };
    if (S.kind === "limit") {
      const p = parseFloat($("#f-price").value);
      if (!(p > 0)) return toast("Enter a limit price", "bad");
      o.price = p; o.qty = q;
    } else if (S.unit === "EUR") o.eur_amount = q;
    else o.qty = q;
    $("#f-submit").disabled = true;
    worker.postMessage({ type: "order", order: o });
  };
  setSide("buy"); setKind("limit");
})();
