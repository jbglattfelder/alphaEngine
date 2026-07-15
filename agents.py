"""
agents.py — Agent state and behaviour for the Alpha Engine POC.

Contains the Agent data structure and the Population that manages all 2n agents.
This module owns everything an agent *is* and *does to itself*: the Pareto
capital draw, balance initialisation, carry/pressure accumulation, firing and
order sizing, mark-to-market, and bankruptcy.

It contains NO market logic — no queue, no auction, no matching. When an agent
fires it returns a plain (agent, size) pair; the simulation turns that into a
queue order. This keeps agents.py and market.py fully decoupled (§21).

Target runtime: Python 3.13 (runs unchanged on 3.12).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Optional

import json
import math
from decimal import Decimal, getcontext
import numpy as np

from config import Config
from position import Position


def _norm_ppf(u: float, prec: int = 60) -> Decimal:
    """Wichura AS241 inverse normal CDF evaluated in `decimal`.

    Same portability reason as the Pareto path: math.log/erfinv route through libm,
    which is not correctly-rounded, so ARM and x86 differ in the last bit. Decimal's
    ln() and sqrt() have specified semantics -> identical bits on any CPU.
    Accurate to ~1e-14 absolute.
    """
    getcontext().prec = prec
    D = Decimal
    p = D(u); q = p - D("0.5")
    if abs(q) <= D("0.425"):
        r = D("0.180625") - q * q
        num = (((((((D("2509.0809287301226727")*r+D("33430.575583588128105"))*r+D("67265.770927008700853"))*r
               +D("45921.953931549871457"))*r+D("13731.693765509461125"))*r+D("1971.5909503065514427"))*r
               +D("133.14166789178437745"))*r+D("3.387132872796366608"))
        den = (((((((D("5226.495278852545925")*r+D("28729.085735721942674"))*r+D("39307.89580009271061"))*r
               +D("21213.794301586595867"))*r+D("5394.1960214247511077"))*r+D("687.1870074920579083"))*r
               +D("42.313330701600911252"))*r+D(1))
        return q * num / den
    r = p if q < 0 else D(1) - p
    r = (-r.ln()).sqrt()
    if r <= D(5):
        r -= D("1.6")
        num = (((((((D("7.7454501427834140764e-4")*r+D("0.0227238449892691845833"))*r+D("0.24178072517745061177"))*r
               +D("1.27045825245236838258"))*r+D("3.64784832476320460504"))*r+D("5.7694972214606914055"))*r
               +D("4.6303378461565452959"))*r+D("1.42343711074968357734"))
        den = (((((((D("1.05075007164441684324e-9")*r+D("5.475938084995344946e-4"))*r+D("0.0151986665636164571966"))*r
               +D("0.14810397642748007459"))*r+D("0.68976733498510000455"))*r+D("1.6763848301838038494"))*r
               +D("2.05319162663775882187"))*r+D(1))
    else:
        r -= D(5)
        num = (((((((D("2.01033439929228813265e-7")*r+D("2.71155556874348757815e-5"))*r+D("0.0012426609473880784386"))*r
               +D("0.026532189526576123093"))*r+D("0.29656057182850489123"))*r+D("1.7848265399172913358"))*r
               +D("5.4637849111641143699"))*r+D("6.6579046435011037772"))
        den = (((((((D("2.04426310338993978564e-15")*r+D("1.4215117583164458887e-7"))*r+D("1.8463183175100546818e-5"))*r
               +D("7.868691311456132591e-4"))*r+D("0.0148753612908506148525"))*r+D("0.13692988092273580531"))*r
               +D("0.59983220655588793769"))*r+D(1))
    val = num / den
    return -val if q < 0 else val


class Side(enum.Enum):
    LONG = "LONG"     # starts EUR-heavy; mandate: sell EUR, buy BTC; home currency = EUR
    SHORT = "SHORT"   # starts BTC-heavy; mandate: sell BTC, buy EUR; home currency = BTC

    def __str__(self) -> str:  # nicer logging / plots
        return self.value


@dataclass
class Agent:
    """One market participant. Side is fixed for life (Lane model, §5)."""
    id: int
    side: Side
    eur: float           # EUR balance
    btc: float           # BTC balance
    K0: float            # initial total capital in EUR terms (retained for threshold scaling)
    d: float             # firing threshold (scales with K0; §7)
    phi: float = 0.0     # accumulated carry pressure — the agent's internal clock (§6)
    K: float = 0.0       # derived: eur + btc * p_int — set via mark_to_market()
    alive: bool = True
    pos: Position = field(default_factory=Position)   # CURRENT open position (reset on close)
    closing: bool = False        # committed to unwinding the open position (SL fired)
    realized_pnl: float = 0.0    # banked PnL (EUR) from closed positions
    realized_base: float = 0.0   # banked PnL (BTC) from home-mode short settles: the coin
                                 # residual is a LIVE asset, so it must be banked in coins
                                 # (a frozen EUR mark would break the zero-sum identity)
    open_ref: Optional[int] = None   # unused in hybrid (entries are market flow)
    tp_ref: Optional[int] = None     # resting TP limit (the book's standing depth)
    close_ref: Optional[int] = None  # resting reduce-only SL close limit (sl_mode="limit")
    sl_level: Optional[float] = None # SL trigger line (dormant until price touches)
    sl_is_buy: bool = False          # SL close direction: buy (short) vs sell (long)
    opened_ever: bool = False        # has this agent ever opened a position
    entry_q: float = 0.0             # |q| right after opening (entry notional, EUR) — for the trade log
    entry_tick: int = 0              # tick the position opened — for lifetime/drift analysis
    req_q: float = 0.0               # EUR notional REQUESTED at fire (size*p_prev) — for gamma = filled-vs-requested
    conv_live: bool = True           # sizing convention (conv_mode="mixed"): convert at live price vs at x_0

    # ── derived views ─────────────────────────────────────────────────────────
    @property
    def home_balance(self) -> float:
        """The balance in the currency the agent is mandated to sell."""
        return self.eur if self.side is Side.LONG else self.btc

    @property
    def is_flat(self) -> bool:
        """No open position (ready to open on pressure)."""
        return self.pos.b == 0.0

    def total_pnl(self, p_int: float) -> float:
        """Realized (closed) + unrealized (current open) trade PnL in EUR.
        Coin-banked PnL (realized_base) is marked at the CURRENT price — it is
        held coins, not frozen EUR — which keeps PnL exactly zero-sum."""
        return self.realized_pnl + self.realized_base * p_int + self.pos.pnl_quote(p_int)

    def mark_to_market(self, p_int: float) -> float:
        """Recompute total capital in EUR terms at the current internal price (§3)."""
        self.K = self.eur + self.btc * p_int
        return self.K

    # ── per-tick mechanics ────────────────────────────────────────────────────
    def accumulate_pressure(self, cfg: Config) -> None:
        """Flat pressure increment — drives OPEN timing only (§6). Accrues only
        while flat; a committed position doesn't build phantom open-pressure."""
        if self.is_flat:
            self.phi += cfg.c

    def ready_to_fire(self) -> bool:
        return self.alive and self.phi >= self.d

    def open_btc(self, cfg: Config, price: float) -> float:
        """Opening size in BTC (CLOB). Long deploys eur/q of EUR; short sells btc/q
        of BTC. Symmetric notional; capped at what the agent holds."""
        if price <= 0:
            return 0.0
        if cfg.x_accounting:
            rp = math.sqrt(price)
            W_X = self.eur / rp + self.btc * rp        # wealth in geometric-mean units
            size = (W_X / cfg.q) / rp                  # BTC order, identical formula both tribes
            # cap at what the agent can actually trade, or the balanced entry crossing
            # (which does not clamp) drives balances negative and breaks x0-conservation.
            if self.side is Side.LONG:
                return min(size, self.eur / price)     # buying BTC: limited by EUR affordable
            return min(size, self.btc)                 # selling BTC: limited by BTC held
        if cfg.conv_mode == "mixed":                            # per-agent convention (overrides the flags below)
            if self.side is Side.LONG:
                return (self.eur / cfg.q) / (price if self.conv_live else cfg.x_0)
            size = self.btc / cfg.q
            return size * (cfg.x_0 / price) if self.conv_live else size
        if cfg.mirror:                                          # x->1/x: the /p conversion rides the OTHER tribe
            if self.side is Side.LONG:
                return self.eur / cfg.q / cfg.x_0               # long now flat
            return (self.btc / cfg.q) * (cfg.x_0 / price)       # short now carries /p
        if cfg.invariant_sizing:                                # numeraire-covariant: p^{-1/2}, both tribes
            return (cfg.f * self.K0 / cfg.q) * (cfg.x_0 / price) ** cfg.sizing_power
        if cfg.frozen_sizing:                                   # fixed per agent, no wealth feedback
            return cfg.f * self.K0 / cfg.q / cfg.x_0
        if self.side is Side.LONG:
            budget = self.eur / cfg.q
            ref = cfg.x_0 if cfg.symmetric_sizing else price    # /x_0 => price-independent size
            return max(0.0, min(budget, self.eur)) / ref
        return max(0.0, min(self.btc / cfg.q, self.btc))        # BTC sold

    def tp_price(self, cfg: Config) -> float:
        """Passive take-profit limit price from entry x̄. Long sells above, short buys below."""
        x = self.pos.avg_price
        if cfg.log_thresholds:
            return x * math.exp(cfg.tp) if self.side is Side.LONG else x * math.exp(-cfg.tp)
        return x * (1 + cfg.tp) if self.side is Side.LONG else x * (1 - cfg.tp)

    def sl_price(self, cfg: Config) -> float:
        """Stop trigger price from entry x̄. Long stops below, short stops above."""
        x = self.pos.avg_price
        if cfg.log_thresholds:
            return x * math.exp(-cfg.sl) if self.side is Side.LONG else x * math.exp(cfg.sl)
        return x * (1 - cfg.sl) if self.side is Side.LONG else x * (1 + cfg.sl)

    def reset_pressure(self) -> None:
        """Full reset after acting (§8)."""
        self.phi = 0.0

    def clear_orders(self) -> None:
        """Forget order refs and trigger lines after a position fully closes."""
        self.open_ref = self.tp_ref = self.close_ref = None
        self.sl_level = None
        self.closing = False


@dataclass
class House:
    """v1 central market maker: a funded counterparty with its own EUR/BTC reserve.

    A funded counterparty. When bailouts are on it swaps home currency to
    compositionally-stuck agents at p_int, funded from its reserve (can freeze).
    Phase 0: economically dormant unless house_bailout is set; future spread income
    arrives with external actors.
    """
    eur: float = 0.0
    btc: float = 0.0
    pos: Position = field(default_factory=Position)   # trade tally (house PnL)

    def value(self, p_int: float) -> float:
        return self.eur + self.btc * p_int

    @classmethod
    def seed(cls, cfg: Config) -> "House":
        v = cfg.house_reserve_frac * cfg.K          # total reserve in EUR terms
        return cls(eur=v / 2.0, btc=(v / 2.0) / cfg.x_0)   # split 50/50 at x_0


class Population:
    """Owns all 2n agents and the operations that act on the whole population."""

    def __init__(self, cfg: Config, rng: Optional[np.random.Generator] = None) -> None:
        self.cfg = cfg
        self.rng = rng if rng is not None else np.random.default_rng(cfg.seed)
        self.agents: list[Agent] = []
        self._build()

    # ── construction ──────────────────────────────────────────────────────────
    def _draw_capital(self, count: int) -> np.ndarray:
        """
        Draw `count` capitals from a Pareto(x_min, alpha) then rescale so the
        group sums to K/2 in EUR terms (§4).

        Portability: rng.pareto() calls libm pow(), which IEEE-754 does NOT require
        to be correctly rounded -- ARM and x86 disagree in the last bit. The model is
        chaotic, so one ulp here rewrites the entire history. Instead we draw exact
        uniforms (PCG64 is integer arithmetic, bit-identical everywhere) and apply the
        inverse-CDF x = (1-u)^(-1/alpha) in `decimal`, a software float with specified
        semantics. Same bits on any CPU. Cost is ~2n Decimal ops, once, at init.
        """
        getcontext().prec = 60
        cfg = self.cfg
        u = self.rng.random(count)                       # exact, portable bit stream
        if cfg.capital_dist == "normal":
            # homogeneous population: K0 ~ N(mu, (cv*mu)^2), truncated at floor*mu > 0.
            mu = Decimal(str(cfg.K / 2.0)) / Decimal(count)
            sd = mu * Decimal(str(cfg.capital_cv))
            lo = mu * Decimal(str(cfg.capital_floor))
            raw = np.array([float(max(mu + sd * _norm_ppf(float(ui)), lo)) for ui in u])
        else:
            inv_a = Decimal(1) / Decimal(str(cfg.alpha))
            xmin = Decimal(str(cfg.x_min))
            raw = np.array([float((Decimal(1) - Decimal(float(ui))) ** (-inv_a) * xmin)
                            for ui in u])
        target = cfg.K / 2.0
        # math.fsum is correctly rounded and order-independent: np.sum's pairwise/SIMD
        # order varies with numpy version/CPU, perturbing every K0 by ~1 ulp. The model
        # is chaotic, so that 1-ulp seed diverges trajectories entirely. Reproducibility
        # across machines requires this. Do not revert to raw.sum().
        return raw * (target / math.fsum(raw))

    def _clock_thresholds(self, all_k0: np.ndarray):
        """Return d(K0), the pressure threshold: agent fires every d/c ticks.

        d = (K0 / mean(K0))^beta, renormalised so mean(d) = 1.

        NB an earlier version used d = K0/min(K0). That denominator is a MIN-statistic: it
        swings with the draw, collapses as dispersion grows, and silently rescales the whole
        market's pace (one unlucky small agent freezes everyone). It made higher capital
        dispersion look like it destroyed liquidity; with the mean it does the opposite.
        mean(K0) == K/(2n) EXACTLY (the draw is rescaled), so the pace is draw-independent
        and set purely by c. beta then dials the size<->rate coupling in isolation:
          beta = 1 : big agents fire proportionally rarely (legacy behaviour)
          beta = 0 : every agent fires at the same rate; capital affects size only
        The renormalisation matters: E[(K0/mu)^beta] <= 1 by Jensen for beta<1, so without
        it, lowering beta would also speed up the average clock and confound the experiment.
        """
        cfg = self.cfg
        mu = float(all_k0.mean())                       # == K/(2n) by construction
        d_raw = (all_k0 / mu) ** cfg.clock_beta
        scale = float(d_raw.mean())                     # fix mean(d) = 1: pace is beta-invariant
        return lambda k0: ((k0 / mu) ** cfg.clock_beta) / scale

    def _build(self) -> None:
        cfg = self.cfg
        k0_long = self._draw_capital(cfg.n)
        k0_short = self._draw_capital(cfg.n)
        all_k0 = np.concatenate([k0_long, k0_short])
        k0_min = float(all_k0.min())
        d_of = self._clock_thresholds(all_k0)  # population-wide smallest agent (§7)

        agents: list[Agent] = []
        aid = 0
        for k0 in k0_long:   # LONG: EUR-heavy
            eur = k0 * cfg.f
            btc = k0 * (1.0 - cfg.f) / cfg.x_0
            agents.append(Agent(id=aid, side=Side.LONG, eur=eur, btc=btc,
                                K0=float(k0), d=d_of(float(k0))))
            aid += 1
        for k0 in k0_short:  # SHORT: BTC-heavy
            btc = k0 * cfg.f / cfg.x_0
            eur = k0 * (1.0 - cfg.f)
            agents.append(Agent(id=aid, side=Side.SHORT, eur=eur, btc=btc,
                                K0=float(k0), d=d_of(float(k0))))
            aid += 1

        if cfg.phase_jitter:                            # break the artificial t=0 synchrony:
            # dedicated stream: jitter must NOT shift the capital draw's bit stream,
            # or jitter-on vs jitter-off would be two different runs, not an A/B.
            jrng = np.random.default_rng((cfg.seed or 0) + 90210)
            for ag in agents:                           # phi_0 ~ U(0, d) staggers first fires
                ag.phi = float(jrng.random()) * ag.d
        if cfg.conv_mode == "mixed":
            # exactly round(conv_mix*n) live-converters per tribe. Assignment by draw
            # index is deterministic and uncorrelated with capital (draws are iid).
            ml = cfg.conv_mix if cfg.conv_mix_long is None else cfg.conv_mix_long
            ms = cfg.conv_mix if cfg.conv_mix_short is None else cfg.conv_mix_short
            kl, ks = round(ml * cfg.n), round(ms * cfg.n)
            for i, ag in enumerate(agents):
                k = kl if ag.side is Side.LONG else ks
                ag.conv_live = (i % cfg.n) < k
        self.agents = agents
        self.k0_min = k0_min
        for a in self.agents:
            a.mark_to_market(cfg.x_0)  # K at the initial price

    # ── baseline used by the order-size regime split ──────────────────────────
    @property
    def order_baseline(self) -> float:
        return self.cfg.x_min if self.cfg.baseline_metric == "x_min" else self.k0_min

    # ── iteration helpers ─────────────────────────────────────────────────────
    def alive(self) -> Iterator[Agent]:
        return (a for a in self.agents if a.alive)

    def by_id(self) -> dict[int, Agent]:
        return {a.id: a for a in self.agents}

    # ── whole-population per-tick steps (called by the simulation loop) ────────
    def accrue_pressure(self, p_int_prev: float) -> None:
        """Loop step 1: pressure up (flat agents only), capital re-marked at p_int(t-1)."""
        for a in self.alive():
            a.accumulate_pressure(self.cfg)
            a.mark_to_market(p_int_prev)

    def apply_bankruptcies(self, p_int: float) -> list[int]:
        """
        Loop step 5 (§15): mark dead anyone at/under epsilon. Returns the ids of
        the newly dead so the simulation can purge their resting orders.

        The death test is valued per cfg.bankruptcy_price: "p_int" (instantaneous
        mark — can kill BTC-heavy agents on a transient price crash) or "x_0"
        (price-invariant real capital — kills only genuine insolvency). K is still
        kept as the p_int mark for recording.
        """
        x0 = self.cfg.x_0
        use_x0 = self.cfg.bankruptcy_price == "x_0"
        dead: list[int] = []
        for a in self.alive():
            a.mark_to_market(p_int)
            bank_val = (a.eur + a.btc * x0) if use_x0 else a.K
            if bank_val <= self.cfg.epsilon:
                a.alive = False
                dead.append(a.id)
        return dead

    # ── observables ───────────────────────────────────────────────────────────
    def alive_count(self) -> tuple[int, int]:
        longs = sum(1 for a in self.agents if a.alive and a.side is Side.LONG)
        shorts = sum(1 for a in self.agents if a.alive and a.side is Side.SHORT)
        return longs, shorts

    def total_capital(self, p_int: float) -> float:
        return float(sum(a.mark_to_market(p_int) for a in self.alive()))

    # ── visualisation ─────────────────────────────────────────────────────────
    def plot_capital_distribution(self, metric: str = "K0",
                                  save_path: Optional[str] = None,
                                  show: bool = False):
        """
        Plot the capital distribution across long vs short agents.

        metric : "K0" for initial capital (default), or "K" for current
                 mark-to-market capital — useful *after* a run to see who drained.

        Two panels:
          (left)  log-binned histogram of capital by side, with the order-size
                  baseline marked — shows the Pareto bulk and where the all-in /
                  fractional trade regimes split.
          (right) empirical CCDF on log-log axes — a straight line signals the
                  power-law tail; its slope is the tail index (~ alpha).

        Returns the matplotlib Figure (so it can be saved or embedded).
        """
        import matplotlib.pyplot as plt  # lazy: core agent mechanics stay plot-free

        if metric not in ("K0", "K"):
            raise ValueError("metric must be 'K0' or 'K'")

        def vals(side: Side) -> np.ndarray:
            return np.asarray(
                [(a.K0 if metric == "K0" else a.K)
                 for a in self.agents if a.side is side and a.alive],
                dtype=float,
            )

        longs, shorts = vals(Side.LONG), vals(Side.SHORT)
        allv = np.concatenate([longs, shorts]) if (len(longs) + len(shorts)) else np.array([1.0])

        fig, (axh, axc) = plt.subplots(1, 2, figsize=(11, 4.2))

        # left — log-binned histogram by side
        bins = np.logspace(np.log10(max(allv.min(), 1e-9)), np.log10(allv.max()), 30)
        axh.hist(longs, bins=bins, alpha=0.55, color="#2563EB", label=f"long (n={len(longs)})")
        axh.hist(shorts, bins=bins, alpha=0.55, color="#B45309", label=f"short (n={len(shorts)})")
        # note: cfg.x_min is the PRE-rescale Pareto floor; after rescaling the draws
        # to sum K/2 the actual minimum shifts, so mark the real post-rescale minimum.
        axh.axvline(self.k0_min, color="#15803D", ls="--", lw=1.2,
                    label=f"smallest K0 (post-rescale) = {self.k0_min:,.0f}")
        axh.set_xscale("log")
        axh.set_xlabel(f"capital ({metric}, EUR terms)")
        axh.set_ylabel("agent count")
        axh.set_title("Capital distribution by side")
        axh.legend(fontsize=8)
        axh.grid(True, which="both", ls=":", alpha=0.4)

        # right — empirical CCDF (survival function), log-log
        for arr, lbl, col in [(longs, "long", "#2563EB"), (shorts, "short", "#B45309")]:
            if len(arr) == 0:
                continue
            sd = np.sort(arr)[::-1]
            ccdf = np.arange(1, len(sd) + 1) / len(sd)
            axc.loglog(sd, ccdf, marker=".", ls="none", ms=5, alpha=0.7, color=col, label=lbl)
        axc.set_xlabel(f"capital ({metric})")
        axc.set_ylabel("P(X >= x)")
        axc.set_title(f"Tail (CCDF, log-log) - Pareto alpha={self.cfg.alpha}")
        axc.legend(fontsize=8)
        axc.grid(True, which="both", ls=":", alpha=0.4)

        med_l = np.median(longs) if len(longs) else float("nan")
        med_s = np.median(shorts) if len(shorts) else float("nan")
        fig.suptitle(
            f"Alpha Engine - agent capital  |  total={allv.sum():,.0f} EUR  "
            f"|  median L/S = {med_l:,.0f} / {med_s:,.0f}", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.95))

        if save_path:
            fig.savefig(save_path, dpi=130, bbox_inches="tight")
        if show:
            plt.show()
        return fig


if __name__ == "__main__":
    # Self-check: build a small population and verify the spec's invariants.
    cfg = Config(n=5, K=100_000, seed=7)
    pop = Population(cfg)

    long_sum = sum(a.K0 for a in pop.agents if a.side is Side.LONG)
    short_sum = sum(a.K0 for a in pop.agents if a.side is Side.SHORT)
    print(f"K0 sum  long={long_sum:,.2f}  short={short_sum:,.2f}  (each target {cfg.K/2:,.0f})")

    # K0 reconstruction: eur + btc*x_0 == K0 for every agent
    ok = all(abs((a.eur + a.btc * cfg.x_0) - a.K0) < 1e-6 for a in pop.agents)
    print("K0 reconstruction holds:", ok)

    # smallest agent has d == d_base
    smallest = min(pop.agents, key=lambda a: a.K0)
    print(f"smallest K0={smallest.K0:,.2f}  d={smallest.d:.4f}  (D_BASE=1.0)")

    # carry drains the home balance; pressure builds
    a0 = pop.agents[0]
    phi_before = a0.phi
    a0.accumulate_pressure(cfg)
    print(f"agent0 phi {phi_before} -> {a0.phi}")

    # firing produces a positive size and resets pressure
    a0.phi = a0.d
    size = a0.open_btc(cfg, cfg.x_0)
    a0.reset_pressure()
    print(f"agent0 fired open size={size:,.4f} BTC  phi after reset={a0.phi}")

    # capital distribution plot on a full-size population
    big = Population(Config(seed=42))
    big.plot_capital_distribution(metric="K0", save_path="capital_distribution.png")
    print("saved capital_distribution.png")
