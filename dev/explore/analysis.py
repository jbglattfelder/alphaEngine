"""
analysis.py — recording, visualisation, and automated correctness checks.

Recorder : the canonical time-series recorder injected into the Simulation.
           Exposes record(**fields), a history dict-of-lists, plus series()/array().

Analyser : consumes a completed Simulation and provides
             - run_sanity_checks() : the §24 assertions (corrected), fail-loud
             - plot_dashboard()    : the §18 panels (price, survivors, drain, queue,
                                     matched volume) plus a report panel
             - report()            : prints the run summary and the check table

The §24 checks, corrected where the spec was internally inconsistent:
  * monotonic capital drain is asserted on total_capital_x0 (price-invariant),
    not the mark-to-market series (which legitimately rises when p_int rises).
  * "matched_volume <= queue_depth" mixed capital units with an order count; it is
    replaced by an internal-consistency check matched_eur == matched_btc * p_int on
    crossed ticks (and zero matched volume on no-cross ticks), which is the real
    content. Per-trade EUR/BTC conservation is enforced live in the loop.

Target runtime: Python 3.13 (runs unchanged on 3.12).
"""

from __future__ import annotations

from typing import Optional

import numpy as np


class Recorder:
    """Append-only time-series store. One list per recorded field."""

    def __init__(self) -> None:
        self.history: dict[str, list] = {}

    def record(self, **fields) -> None:
        for k, v in fields.items():
            self.history.setdefault(k, []).append(v)

    def series(self, name: str) -> list:
        return self.history.get(name, [])

    def array(self, name: str) -> np.ndarray:
        return np.asarray(self.history.get(name, []))


class Analyser:
    """Sanity checks and visualisation over a completed Simulation."""

    def __init__(self, sim) -> None:
        self.sim = sim
        self.cfg = sim.cfg
        self.rec = sim.recorder

    # ── correctness (§24, corrected) ──────────────────────────────────────────
    def run_sanity_checks(self, raise_on_fail: bool = True) -> list[tuple[str, bool, str]]:
        results: list[tuple[str, bool, str]] = []

        def add(name: str, ok: bool, detail: str = "") -> None:
            results.append((name, bool(ok), detail))

        # monotone conserved capital: v1 uses system (agents+house); v0 uses agents alone
        cap_key = "system_x0" if "system_x0" in self.rec.history else "total_capital_x0"
        capx0 = self.rec.array(cap_key)
        if capx0.size > 1:
            diffs = np.diff(capx0)
            tol = 1e-6 * max(abs(capx0[0]), 1.0)
            add(f"{cap_key} monotone non-increasing", np.all(diffs <= tol),
                f"max tick-over-tick increase = {diffs.max():.3e}")

        pint = self.rec.array("p_int")
        if pint.size:
            add("p_int strictly positive", np.all(pint > 0), f"min = {pint.min():.6g}")

        crossed = self.rec.array("crossed").astype(bool)
        meur = self.rec.array("matched_eur")
        mbtc = self.rec.array("matched_btc")
        if crossed.any():
            # CLOB fills at many maker prices per tick, so meur != mbtc*p_int in general.
            # Valid invariant: the tick VWAP (meur/mbtc) is a positive, finite price.
            vwap = meur[crossed] / np.maximum(mbtc[crossed], 1e-30)
            add("tick VWAP positive & finite (crossed)",
                np.all(np.isfinite(vwap)) and np.all(vwap > 0),
                f"VWAP range [{vwap.min():.3g}, {vwap.max():.3g}]")
        if (~crossed).any():
            add("zero matched volume on no-cross ticks",
                np.all(meur[~crossed] == 0) and np.all(mbtc[~crossed] == 0))

        al, ash = self.rec.array("alive_long"), self.rec.array("alive_short")
        if al.size:
            add("alive_long + alive_short <= 2n",
                np.all(al + ash <= self.cfg.total_agents),
                f"peak = {int((al + ash).max())}")

        # PnL is zero-sum across longs + shorts + house (no spread yet).
        # GAUGE: the residual is float coin-dust (BTC roundoff in the balanced
        # crossing, ~1e-10 BTC on 1e6 totals). Marked in EUR it scales with p, so a
        # fixed EUR tolerance false-alarms in wide-excursion worlds (p spanning 20+
        # e-folds turns 1e-11 BTC into macroscopic EUR). Test in the X unit
        # (net/sqrt(p)), which is numeraire-covariant; tol = 1e-9 of total capital
        # in X — float-dust passes, any real transfer leak (O(agent capital)) fails.
        if "pnl_long" in self.rec.history:
            net = (self.rec.array("pnl_long") + self.rec.array("pnl_short")
                   + self.rec.array("pnl_house"))
            pint_ = self.rec.array("p_int")
            net_x = np.abs(net) / np.sqrt(np.maximum(pint_, 1e-300))
            tol_x = 1e-9 * self.cfg.K
            add("PnL zero-sum (X-gauge, long+short+house = 0)",
                np.all(net_x <= tol_x),
                f"max |net|_X = {net_x.max():.3e} (tol {tol_x:.1e})")

        # structural: no dead agent rests an order in the final book
        by_id = self.sim.pop.by_id()
        resting = [o for o in (self.sim.book.bids + self.sim.book.asks) if o.active]
        no_dead = all(by_id[o.agent_id].alive for o in resting)
        add("no dead agent in final book", no_dead,
            f"{len(resting)} resting orders")

        # per-agent solvency: no agent holds negative EUR or BTC. Absent this check a
        # small cover-path leak (unclamped balanced-crossing fills on stuck SL covers)
        # slips past the system_x0 monotonicity tolerance. tol scales with model units.
        tol = 1e-6 * self.cfg.x_min
        min_eur = min((a.eur for a in self.sim.pop.agents), default=0.0)
        min_btc = min((a.btc for a in self.sim.pop.agents), default=0.0)
        add("per-agent solvency (eur, btc >= 0)",
            min_eur >= -tol and min_btc >= -tol,
            f"min eur = {min_eur:.4g}, min btc = {min_btc:.4g}")

        failed = [r for r in results if not r[1]]
        if raise_on_fail and failed:
            lines = "\n".join(f"  FAIL  {n}  ({d})" for n, _, d in failed)
            raise AssertionError("Sanity checks failed:\n" + lines)
        return results


    # ── wealth / inequality (numeraire-invariant) ─────────────────────────────
    @staticmethod
    def geom_wealth(eur, btc, p):
        """Numeraire-invariant wealth: sqrt(W_base * W_quote).

        W_quote = eur + p*btc     (value in EUR)
        W_base  = eur/p + btc     (value in BTC)
        Under p -> 1/p the two swap, so their product -- and this wealth -- is invariant.
        """
        eur = np.asarray(eur, float); btc = np.asarray(btc, float)
        return np.sqrt((eur / p + btc) * (eur + p * btc))

    @staticmethod
    def gini(x):
        x = np.sort(np.asarray(x, float)); n = len(x)
        if n == 0 or x.sum() <= 0:
            return float("nan")
        return (2.0 * np.sum(np.arange(1, n + 1) * x) / (n * x.sum())) - (n + 1.0) / n

    def wealth_concentration(self, price=None) -> dict:
        """Did TRADING concentrate wealth? Compare t=0 and t=T holdings at ONE price.

        WARNING -- the trap this method exists to prevent: valuing t=0 at x_0 and t=T at
        p_final does NOT measure concentration. Geometric wealth scales as eur/sqrt(p) for
        a EUR-heavy agent and btc*sqrt(p) for a BTC-heavy one, so any price move splits the
        long (EUR-home) and short (BTC-home) tribes apart with zero trading. That artifact is
        ~100x larger than the real effect and correlates 0.91 with |ln p_final|.
        Fixing the price kills the valuation channel; what remains is redistribution.
        """
        sim = self.sim
        p = self.cfg.x_0 if price is None else price
        eurT = np.array([a.eur for a in sim.pop.agents])
        btcT = np.array([a.btc for a in sim.pop.agents])
        g0 = self.gini(self.geom_wealth(sim.eur0, sim.btc0, p))
        gT = self.gini(self.geom_wealth(eurT, btcT, p))
        return {"price": p, "gini_0": g0, "gini_T": gT, "d_gini": gT - g0,
                "gini_T_at_p_final": self.gini(self.geom_wealth(eurT, btcT, sim.p_int))}

    # ── reporting ─────────────────────────────────────────────────────────────
    def report(self) -> None:
        print(self.sim.summary())
        print("Sanity checks")
        for name, ok, detail in self.run_sanity_checks(raise_on_fail=False):
            flag = "PASS" if ok else "FAIL"
            tail = f"   ({detail})" if detail else ""
            print(f"  [{flag}] {name}{tail}")

    # ── visualisation (§18) ───────────────────────────────────────────────────
    @staticmethod
    def _bin(t, y, nbins=900):
        """Downsample a long, spiky series into per-bin statistics.

        Returns an object with arrays: .t (bin centre), .mean, .lo (min),
        .hi (max), .std, .total (sum). This keeps the panels clean at 100k ticks
        (no per-pixel smear / false t=0 wall) while letting each panel pick the
        right reduction: average the stocks (depth), sum the flows (volume),
        show spread with std.
        """
        from types import SimpleNamespace
        n = len(t)
        if n <= nbins:                       # too short to bin: pass through raw
            z = np.zeros_like(np.asarray(y, dtype=float))
            return SimpleNamespace(t=t, mean=y, lo=y, hi=y, std=z, total=y)
        edges = np.linspace(0, n, nbins + 1, dtype=int)
        tc, mean, lo, hi, std, total = [], [], [], [], [], []
        for i in range(nbins):
            a, b = edges[i], edges[i + 1]
            if b <= a:
                continue
            seg = y[a:b]
            tc.append(t[a:b].mean())
            mean.append(seg.mean()); lo.append(seg.min()); hi.append(seg.max())
            std.append(seg.std()); total.append(seg.sum())
        return SimpleNamespace(
            t=np.asarray(tc), mean=np.asarray(mean), lo=np.asarray(lo),
            hi=np.asarray(hi), std=np.asarray(std), total=np.asarray(total))

    def plot_pnl_distribution(self, save_path: Optional[str] = None, show: bool = False):
        """Who's winning and losing — distribution of per-agent trade PnL (EUR).

        (left)   final per-agent PnL histogram, long vs short
        (middle) PnL vs initial capital K0 (log x) — does size predict winning?
        (right)  PnL percentile bands over time (needs snapshot_every > 0), else
                 a note. Shows whether the win/loss spread widens (inequality).
        """
        import matplotlib.pyplot as plt
        BLUE, ORANGE, GREY = "#2563EB", "#C2680A", "#9CA3AF"
        sim = self.sim
        p = sim.p_int
        pnl = np.array([a.total_pnl(p) for a in sim.pop.agents])
        is_long = sim.agent_is_long
        k0 = sim.agent_k0

        fig, (axh, axs, axe) = plt.subplots(1, 3, figsize=(16, 4.6))

        # left — final PnL histogram by side
        lo, hi = np.percentile(pnl, [1, 99])
        bins = np.linspace(min(lo, -1), max(hi, 1), 41)
        axh.hist(pnl[is_long], bins=bins, alpha=0.6, color=BLUE, label=f"long (n={is_long.sum()})")
        axh.hist(pnl[~is_long], bins=bins, alpha=0.6, color=ORANGE, label=f"short (n={(~is_long).sum()})")
        axh.axvline(0, color=GREY, ls=":", lw=1)
        axh.set_title("final PnL distribution by side")
        axh.set_xlabel("trade PnL (EUR)"); axh.set_ylabel("agents")
        axh.legend(fontsize=8, frameon=False)

        # middle — PnL vs initial capital
        axs.axhline(0, color=GREY, ls=":", lw=1)
        axs.scatter(k0[is_long], pnl[is_long], s=10, alpha=0.5, color=BLUE, label="long")
        axs.scatter(k0[~is_long], pnl[~is_long], s=10, alpha=0.5, color=ORANGE, label="short")
        axs.set_xscale("log")
        axs.set_title("PnL vs initial capital K0")
        axs.set_xlabel("K0 (EUR, log)"); axs.set_ylabel("trade PnL (EUR)")
        axs.legend(fontsize=8, frameon=False)

        # right — percentile bands over time
        if sim.snap_pnl:
            ts = np.array(sim.snap_tick)
            M = np.vstack(sim.snap_pnl)                 # [snapshot, agent]
            for plo, phi, a in [(10, 90, 0.18), (25, 75, 0.28)]:
                axe.fill_between(ts, np.percentile(M, plo, axis=1),
                                 np.percentile(M, phi, axis=1), color=BLUE, alpha=a,
                                 label=f"{plo}–{phi}%")
            axe.plot(ts, np.percentile(M, 50, axis=1), color="#111827", lw=1.2, label="median")
            axe.plot(ts, M.max(axis=1), color="#15803D", lw=0.6, label="max")
            axe.plot(ts, M.min(axis=1), color="#DC2626", lw=0.6, label="min")
            axe.axhline(0, color=GREY, ls=":", lw=1)
            axe.set_title("PnL distribution over time (percentile bands)")
            axe.set_xlabel("tick"); axe.set_ylabel("trade PnL (EUR)")
            axe.legend(fontsize=7, frameon=False, ncol=2)
        else:
            axe.text(0.5, 0.5, "run with snapshot_every > 0\nto see PnL evolution",
                     ha="center", va="center", transform=axe.transAxes, color=GREY)
            axe.axis("off")

        fig.suptitle("Alpha Engine — PnL distribution (who wins / loses)", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        if save_path:
            fig.savefig(save_path, dpi=130, bbox_inches="tight")
        if show:
            plt.show()
        return fig

    def plot_dashboard(self, save_path: Optional[str] = None, show: bool = False,
                       price_yscale: str = "log"):
        import matplotlib.pyplot as plt

        if price_yscale not in ("log", "linear"):
            raise ValueError("price_yscale must be 'log' or 'linear'")

        BLUE, ORANGE, PURPLE, TEAL, INK, GREY = (
            "#2563EB", "#C2680A", "#7C3AED", "#0E7490", "#111827", "#9CA3AF")

        t = self.rec.array("tick")
        pint = self.rec.array("p_int")
        crossed = self.rec.array("crossed").astype(bool)

        plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                             "axes.grid": True, "grid.color": "#E5E7EB",
                             "grid.linewidth": 0.6, "font.size": 9})
        fig, axes = plt.subplots(2, 4, figsize=(19, 8))
        a_price, a_alive, a_cap, a_pnl = axes[0]
        a_queue, a_vol, a_xbar, a_text = axes[1]

        # 1 — internal price (log y: tames the freeze-spikes, keeps the band readable)
        a_price.plot(t, pint, color=BLUE, lw=0.6)
        if crossed.any():
            a_price.scatter(t[crossed], pint[crossed], s=4, color="#15803D",
                            alpha=0.35, linewidths=0, label="tick with trades")
        a_price.axhline(self.cfg.x_0, color=GREY, ls=":", lw=1, label="x_0")
        a_price.set_yscale(price_yscale)
        scale_tag = " (log)" if price_yscale == "log" else ""
        a_price.set_title(f"p_int(t) — emergent price{scale_tag}")
        a_price.set_xlabel("tick"); a_price.set_ylabel("EUR/BTC")
        a_price.legend(fontsize=8, frameon=False)

        # 2 — survivors by side
        a_alive.plot(t, self.rec.array("alive_long"), color=BLUE, lw=1.2, label="long")
        a_alive.plot(t, self.rec.array("alive_short"), color=ORANGE, lw=1.2, label="short")
        a_alive.set_ylim(-0.05 * self.cfg.n, self.cfg.n * 1.05)
        a_alive.set_title("alive_count(t) — survivors")
        a_alive.set_xlabel("tick"); a_alive.set_ylabel("agents")
        a_alive.legend(fontsize=8, frameon=False)

        # 3 — pool capital (log y: mark-to-market spikes and the drain curve coexist)
        a_cap.plot(t, self.rec.array("total_capital"), color=PURPLE, lw=0.6, alpha=0.8,
                   label="mark-to-market")
        a_cap.plot(t, self.rec.array("total_capital_x0"), color=INK, lw=1.4,
                   label="agents at x_0 (real)")
        if "house_eur" in self.rec.history:        # v1: house pots (watch them drain/freeze)
            a_cap.plot(t, self.rec.array("house_eur"), color="#16A34A", lw=1.0, ls="--",
                       label="house EUR")
            a_cap.plot(t, self.rec.array("house_btc") * self.cfg.x_0, color="#CA8A04",
                       lw=1.0, ls="--", label="house BTC·x0")
        a_cap.set_yscale(price_yscale)
        a_cap.set_title("total_capital(t) — pool")
        a_cap.set_xlabel("tick"); a_cap.set_ylabel("EUR")
        a_cap.legend(fontsize=8, frameon=False)

        # 4 — book depth: bin mean +/- sigma band (typical spread), faint max line.
        # These are BOOK sides, not agent sides: the bids are shorts' resting TP
        # buybacks and the asks are longs' resting TP sells (open orders never rest).
        for key, col, lbl in (("book_bids", BLUE, "bids (shorts' TPs)"),
                              ("book_asks", ORANGE, "asks (longs' TPs)")):
            b = self._bin(t, self.rec.array(key))
            upper = b.mean + b.std
            lower = np.clip(b.mean - b.std, 0, None)        # depth can't be < 0
            a_queue.fill_between(b.t, lower, upper, color=col, alpha=0.18, linewidth=0)
            a_queue.plot(b.t, b.mean, color=col, lw=1.3, label=lbl)
            a_queue.plot(b.t, b.hi, color=col, lw=0.5, ls=":", alpha=0.5)  # peak excursion
        a_queue.set_ylim(bottom=0)
        a_queue.set_title("book_depth(t) — resting TP limits (bin mean ± σ, dotted = max)")
        a_queue.set_xlabel("tick"); a_queue.set_ylabel("orders")
        a_queue.legend(fontsize=8, frameon=False)

        # 5 — matched volume, in BOTH numeraires (a flow -> binned SUM).
        # EUR volume = BTC volume * p, so a price collapse makes EUR volume vanish even
        # when trading is unchanged: plotting EUR alone shows the PRICE wearing a volume
        # costume. (sqrt(E*B) is invariant under relabelling the numeraire, but equals
        # B*sqrt(p), so it is still price-dependent -- not an activity measure either.)
        # BTC volume and the clear count are the numeraire-free activity measures.
        be = self._bin(t, self.rec.array("matched_eur"))
        bb = self._bin(t, self.rec.array("matched_btc"))
        a_vol.fill_between(be.t, 0, be.total, color=TEAL, alpha=0.45, linewidth=0,
                           label="EUR cleared (price-dependent)")
        a_vol.plot(be.t, be.total, color=TEAL, lw=0.8)
        a_vol.set_ylim(bottom=0)
        a_vol.set_xlabel("tick"); a_vol.set_ylabel("EUR / bin", color=TEAL)
        a_vol.tick_params(axis="y", labelcolor=TEAL)
        a_vol2 = a_vol.twinx()
        a_vol2.plot(bb.t, bb.total, color="#B45309", lw=1.2, label="BTC cleared (activity)")
        a_vol2.set_ylim(bottom=0)
        a_vol2.set_ylabel("BTC / bin", color="#B45309")
        a_vol2.tick_params(axis="y", labelcolor="#B45309")
        a_vol2.grid(False)
        a_vol.set_title("matched_volume(t) — EUR (left) vs BTC (right)")
        h1, l1 = a_vol.get_legend_handles_labels()
        h2, l2 = a_vol2.get_legend_handles_labels()
        a_vol.legend(h1 + h2, l1 + l2, fontsize=7, frameon=False, loc="upper right")

        # 6 — trade PnL (EUR), zero-sum: longs vs shorts (mirror) + house
        a_pnl.axhline(0, color=GREY, lw=0.8, ls=":")
        a_pnl.plot(t, self.rec.array("pnl_long"), color=BLUE, lw=1.1, label="long")
        a_pnl.plot(t, self.rec.array("pnl_short"), color=ORANGE, lw=1.1, label="short")
        a_pnl.plot(t, self.rec.array("pnl_house"), color="#16A34A", lw=1.1, label="house")
        a_pnl.set_title("PnL(t) — trade profit (EUR, zero-sum)")
        a_pnl.set_xlabel("tick"); a_pnl.set_ylabel("EUR")
        a_pnl.legend(fontsize=8, frameon=False)

        # 7 — average entry price x̄ = −ΣQ/ΣB (open positions only) vs p_int
        def side_xbar(side_long: bool) -> float:
            open_agents = [a for a in self.sim.pop.agents
                           if (a.side.name == "LONG") == side_long and abs(a.pos.b) > 1e-12]
            if not open_agents:
                return float("nan")
            sb = sum(a.pos.b for a in open_agents)
            sq = sum(a.pos.q for a in open_agents)
            return float(-sq / sb) if abs(sb) > 1e-12 else float("nan")

        def _fmt(v: float) -> str:
            return f"{v:.3f}" if np.isfinite(v) else "—"

        a_xbar.plot(t, pint, color=GREY, lw=0.5, alpha=0.6, label="p_int")
        a_xbar.axhline(self.cfg.x_0, color=GREY, ls=":", lw=0.8, label="x_0")
        xbar_l, xbar_s = side_xbar(True), side_xbar(False)
        if np.isfinite(xbar_l):
            a_xbar.axhline(xbar_l, color=BLUE, lw=1.2, label=f"long x̄={_fmt(xbar_l)}")
        if np.isfinite(xbar_s):
            a_xbar.axhline(xbar_s, color=ORANGE, lw=1.2, label=f"short x̄={_fmt(xbar_s)}")
        n_open_l = sum(1 for a in self.sim.pop.agents
                       if a.side.name == "LONG" and abs(a.pos.b) > 1e-12)
        n_open_s = sum(1 for a in self.sim.pop.agents
                       if a.side.name == "SHORT" and abs(a.pos.b) > 1e-12)
        a_xbar.set_title(
            f"avg entry x̄=−ΣQ/ΣB  (open: L={n_open_l} S={n_open_s})")
        a_xbar.set_yscale(price_yscale)
        a_xbar.set_xlabel("tick"); a_xbar.set_ylabel("EUR/BTC")
        a_xbar.legend(fontsize=8, frameon=False)

        # 8 — text report panel
        a_text.axis("off")
        lines = [self.sim.summary().rstrip(), "", "Sanity checks"]
        for name, ok, _ in self.run_sanity_checks(raise_on_fail=False):
            lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        a_text.text(0.0, 1.0, "\n".join(lines), va="top", ha="left",
                    family="monospace", fontsize=8, transform=a_text.transAxes)

        fig.suptitle("Alpha Engine — run dashboard", fontsize=13, y=0.99)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        if save_path:
            fig.savefig(save_path, dpi=130, bbox_inches="tight")
        if show:
            plt.show()
        return fig


if __name__ == "__main__":
    from config import Config
    from simulation import Simulation

    # livelier params so the dashboard shows real dynamics
    sim = Simulation(Config(c=0.02, T=1000, seed=42), recorder=Recorder(),
                     run_checks=True).run()
    an = Analyser(sim)
    an.report()
    an.plot_dashboard(save_path="dashboard_demo.png")
    print("\nsaved dashboard_demo.png")
