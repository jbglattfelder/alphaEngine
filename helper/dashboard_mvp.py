"""
dashboard_mvp.py — plots for the MVP null model.

Two figures, consistent titling (the pair is BTC/EUR; the value is EUR per
BTC — standard base/quote notation, same number the engine trades at):

  dashboard_mvp.png — (1) the emergent price, (2) the final PnL distribution
  orderbook_mvp.png — (1) resting order count per side over time,
                      (2) resting volume per side over time (BTC),
                      (3) the DEEPEST book state of the run as a depth diagram

Everything reads the plain recorded lists on a finished Simulation — no
recorder classes, no hidden state.
"""

from __future__ import annotations

import numpy as np

# palette (matches the legacy dashboard's hues so plots stay comparable)
BLUE = "#2563EB"      # longs / bids
ORANGE = "#C2680A"    # shorts / asks
GREEN = "#15803D"     # trades
GREY = "#9CA3AF"


def _bin_mean(x: np.ndarray, y: np.ndarray, n_bins: int = 300):
    """Reduce a long per-tick series to per-bin means for readable plotting.
    Returns (bin_center_x, bin_mean_y). Plotting 100k raw points hides the
    structure and bloats the file; the mean per bin is the honest summary."""
    if len(x) <= n_bins:
        return x, y
    edges = np.linspace(x[0], x[-1], n_bins + 1)
    idx = np.digitize(x, edges) - 1
    idx = np.clip(idx, 0, n_bins - 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    sums = np.bincount(idx, weights=y, minlength=n_bins)
    counts = np.bincount(idx, minlength=n_bins)
    means = np.divide(sums, counts, out=np.zeros(n_bins), where=counts > 0)
    keep = counts > 0
    return centers[keep], means[keep]


def plot_dashboard(sim, save_path: str = "dashboard_mvp.png", show: bool = False):
    """The two-panel MVP dashboard: price evolution + final PnL distribution."""
    import matplotlib.pyplot as plt

    t = np.asarray(sim.rec_tick)
    price = np.asarray(sim.rec_price)
    crossed = np.asarray(sim.rec_crossed, dtype=bool)

    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#E5E7EB",
                         "grid.linewidth": 0.6, "font.size": 10})
    fig, (ax_price, ax_pnl) = plt.subplots(1, 2, figsize=(13, 4.6))

    # ── panel 1: the emergent price ──────────────────────────────────────────
    # the intra-tick wick envelope first (behind the line): min/max print per
    # tick — the flash excursions the last-print-per-tick series cannot show
    hi = getattr(sim, "rec_price_hi", None)
    lo = getattr(sim, "rec_price_lo", None)
    if hi is not None and lo is not None and len(hi) == len(t):
        hi = np.asarray(hi)
        lo = np.asarray(lo)
        if len(t) > 2000:
            # a one-tick wick is sub-pixel at this resolution; aggregate the
            # envelope per bin with MAX(hi)/MIN(lo) so flash needles survive
            # the downsampling instead of vanishing (the candlestick rule)
            n_bins = 1000
            edges = np.linspace(t[0], t[-1], n_bins + 1)
            idx = np.clip(np.digitize(t, edges) - 1, 0, n_bins - 1)
            hi_b = np.full(n_bins, -np.inf)
            lo_b = np.full(n_bins, np.inf)
            np.maximum.at(hi_b, idx, hi)
            np.minimum.at(lo_b, idx, lo)
            centers = 0.5 * (edges[:-1] + edges[1:])
            keep = np.isfinite(hi_b)
            ax_price.fill_between(centers[keep], lo_b[keep], hi_b[keep],
                                  color="#DC2626", alpha=0.30, linewidth=0,
                                  label="intra-tick print range (bin high/low)")
        else:
            ax_price.fill_between(t, lo, hi, color="#DC2626", alpha=0.30,
                                  linewidth=0,
                                  label="intra-tick print range (high/low)")
    ax_price.plot(t, price, color=BLUE, lw=0.7)
    if crossed.any():
        ax_price.scatter(t[crossed], price[crossed], s=3, color=GREEN,
                         alpha=0.3, linewidths=0, label="tick with trades")
    ax_price.axhline(sim.cfg.x_0, color=GREY, ls=":", lw=1,
                     label=f"initial price x_0 = {sim.cfg.x_0}")
    ax_price.set_title("Emergent price — BTC/EUR")
    ax_price.set_xlabel("tick")
    ax_price.set_ylabel("price (EUR per BTC)")
    ax_price.legend(fontsize=8, frameon=False)

    # ── panel 2: final per-agent PnL by side (zero-sum by construction) ─────
    p_final = float(price[-1])
    pnl = []
    is_long = []
    for a in sim.agents:
        pnl.append(a.total_pnl(p_final))
        is_long.append(a.is_long)
    pnl = np.asarray(pnl)
    is_long = np.asarray(is_long)
    lo, hi = np.percentile(pnl, [1, 99])
    bins = np.linspace(min(lo, -1), max(hi, 1), 41)
    ax_pnl.hist(pnl[is_long], bins=bins, alpha=0.6, color=BLUE,
                label=f"long (n={int(is_long.sum())})")
    ax_pnl.hist(pnl[~is_long], bins=bins, alpha=0.6, color=ORANGE,
                label=f"short (n={int((~is_long).sum())})")
    ax_pnl.axvline(0, color=GREY, ls=":", lw=1)
    ax_pnl.set_title(f"Final agent PnL — EUR (zero-sum; Σ = {pnl.sum():+.6f})")
    ax_pnl.set_xlabel("PnL per agent (EUR)")
    ax_pnl.set_ylabel("number of agents")
    ax_pnl.legend(fontsize=8, frameon=False)

    fig.suptitle("Alpha Engine MVP — the frozen null model", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(save_path, dpi=130, bbox_inches="tight")
    if show:
        plt.show()          # pops the IDE window; returns when it is closed
    else:
        plt.close(fig)
    return save_path


def plot_orderbook(sim, save_path: str = "orderbook_mvp.png", show: bool = False):
    """The order-book figure: depth (order count), volume (BTC), and the
    deepest book state of the whole run drawn as a depth diagram.

    Reading guide (all three panels):
      bids = resting BUY orders  — mostly SHORTS' take-profit buybacks,
             below the price, plus flat longs' resting entry residuals.
      asks = resting SELL orders — mostly LONGS' take-profit sells, above
             the price, plus flat shorts' resting entry residuals.
    Liquidity here is other agents' unrealized profit, waiting."""
    import matplotlib.pyplot as plt

    t = np.asarray(sim.rec_tick)
    n_bids = np.asarray(sim.rec_book_bids, dtype=float)
    n_asks = np.asarray(sim.rec_book_asks, dtype=float)
    v_bids = np.asarray(sim.rec_bid_btc)
    v_asks = np.asarray(sim.rec_ask_btc)

    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#E5E7EB",
                         "grid.linewidth": 0.6, "font.size": 10})
    fig, (ax_count, ax_vol, ax_snap) = plt.subplots(1, 3, figsize=(17, 4.8))

    # ── panel 1: how many orders rest in the book ────────────────────────────
    bt, bm = _bin_mean(t, n_bids)
    at_, am = _bin_mean(t, n_asks)
    ax_count.plot(bt, bm, color=BLUE, lw=1.3, label="bids (buy orders resting)")
    ax_count.plot(at_, am, color=ORANGE, lw=1.3, label="asks (sell orders resting)")
    ax_count.set_ylim(bottom=0)
    ax_count.set_title("Book depth — resting orders per side")
    ax_count.set_xlabel("tick")
    ax_count.set_ylabel("number of resting orders (bin mean)")
    ax_count.legend(fontsize=8, frameon=False)

    # ── panel 2: how much volume rests in the book ───────────────────────────
    bt, bm = _bin_mean(t, v_bids)
    at_, am = _bin_mean(t, v_asks)
    ax_vol.plot(bt, bm, color=BLUE, lw=1.3, label="bid volume")
    ax_vol.plot(at_, am, color=ORANGE, lw=1.3, label="ask volume")
    ax_vol.set_ylim(bottom=0)
    ax_vol.set_title("Book volume — resting size per side (BTC)")
    ax_vol.set_xlabel("tick")
    ax_vol.set_ylabel("resting volume (BTC, bin mean)")
    ax_vol.legend(fontsize=8, frameon=False)

    # ── panel 3: the deepest book state of the run, as a depth diagram ──────
    # Classic exchange depth chart: cumulative resting BTC vs price. Bids
    # accumulate walking DOWN from the price, asks walking UP — the two
    # walls a market order has to eat through.
    snap = sim.deepest_snapshot
    p_ref = sim.deepest_price
    bids = sorted([(p, s) for p, s, side in snap if side == "bid"], reverse=True)
    asks = sorted([(p, s) for p, s, side in snap if side == "ask"])
    if bids:
        bp = np.array([p for p, s in bids])
        bc = np.cumsum([s for p, s in bids])
        ax_snap.step(bp, bc, where="post", color=BLUE, lw=1.6)
        ax_snap.fill_between(bp, 0, bc, step="post", color=BLUE, alpha=0.25,
                             label=f"bids ({len(bids)} orders)")
    if asks:
        ap = np.array([p for p, s in asks])
        ac = np.cumsum([s for p, s in asks])
        ax_snap.step(ap, ac, where="post", color=ORANGE, lw=1.6)
        ax_snap.fill_between(ap, 0, ac, step="post", color=ORANGE, alpha=0.25,
                             label=f"asks ({len(asks)} orders)")
    ax_snap.axvline(p_ref, color=GREEN, ls="--", lw=1.2,
                    label=f"last price = {p_ref:.4f}")
    ax_snap.set_title(f"Deepest book state (tick {sim.deepest_tick:,}, "
                      f"{sim.deepest_count} orders)")
    ax_snap.set_xlabel("price (EUR per BTC)")
    ax_snap.set_ylabel("cumulative resting volume (BTC)")
    ax_snap.legend(fontsize=8, frameon=False)

    fig.suptitle("Alpha Engine MVP — the order book "
                 "(liquidity = other agents' unrealized profit)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(save_path, dpi=130, bbox_inches="tight")
    if show:
        plt.show()          # pops the IDE window; returns when it is closed
    else:
        plt.close(fig)
    return save_path
