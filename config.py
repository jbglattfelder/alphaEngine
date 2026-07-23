"""
config.py — The Alpha Engine, single source of truth.

Phase 0 (lean Lane core + dormant house). Carry, beta, order_size_basis, d_base,
and the price-scale plotting toggle have been removed. The house actor is kept
(bookkeeper / residual counterparty / future spread-earner); its bailout policy is
retained behind a flag, defaulted OFF.

Fields are grouped:
  - core        : the durable Lane engine
  - house       : the house actor (durable) + its bailout policy (optional)
  - transitional: kept for Phase 0/1 correctness, RETIRES when positions + TP/SL land

Derived parameters (x_min, epsilon) are computed in __post_init__ when left as None.
Target runtime: Python 3.13 (runs unchanged on 3.12).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Optional

D_BASE = 1.0   # firing threshold of the smallest agent (was config.d_base; fixed — it only sets the time unit: the smallest agent fires every D_BASE/c ticks)


@dataclass
class Config:
    # ── core ──────────────────────────────────────────────────────────────────
    n: int = 150                # agents per side; total population is 2 * n
    K: float = 1_000_000.0      # total initial capital in EUR terms (split K/2 per side)
    x_0: float = 1.0            # initial EUR/BTC price; also p_int(0)
    f: float = 0.5              # home-currency fraction at init (1.0 = pure home, 0.5 = even)
    alpha: float = 1.5          # Pareto scaling exponent (heavier tail as alpha -> 1)
    capital_dist: str = "pareto"  # initial capital law: "pareto" (heavy-tailed) | "normal" (homogeneous)
    capital_cv: float = 0.3     # coefficient of variation, "normal" only (sd = cv * mean)
    capital_floor: float = 0.05 # "normal" only: truncate draws below floor*mean (keeps K0 > 0)
    # ── firing clock: d_i is the pressure threshold; agent i fires every d_i/c ticks ──
    clock_beta: float = 1.0     # capital->firing-rate coupling: d=(K0/meanK0)^beta, renormalised to mean(d)=1.
                                # 1 = big agents fire proportionally rarely (model assumption); 0 = rate independent of size
    phase_jitter: bool = True   # phi_0 ~ U(0, d_i): agents start uniformly in phase (steady state).
                                # False leaves the first 1/c ticks empty -- an initialisation artifact
    x_min: Optional[float] = None   # Pareto minimum / baseline; computed K/(n*10) if None
    c: float = 0.004            # firing rate per tick: smallest agent fires every D_BASE/c ticks (active substrate)
    q: int = 8                  # order fraction: every open deploys home/q (the old all-in/fractional
                                # baseline split is NOT implemented in the CLOB open_btc; see agents.py)
    W: int = 15                 # VESTIGIAL (CLOB era): entries are IOC and TP limits never expire, so
                                # nothing in the book ages out. Kept only for config-file compatibility.
    tp: float = 0.01            # take-profit: close position when its return >= +tp
    sl: float = 0.01            # stop-loss:   close position when its return <= -sl
    sl_grid: float = 0.0        # >0 = snap SL trigger levels to a LOG grid of this spacing.
                                # 0 = off (each agent stops at its own entry*e^-sl, so stops are
                                # SCATTERED and fire one at a time -> no cascade -> thin tails).
                                # Osler (2005, JIMF 24:219) finds FX stop-losses cause price
                                # cascades BECAUSE they cluster near round numbers: hitting a
                                # cluster fires many stops in one tick, aggregating into a large
                                # market order that walks deep and reaches the next cluster.
                                # Log grid (not price grid) because p spans e-folds here, and
                                # round numbers are ~log-spaced in a scale-free market anyway.
    sl_enabled: bool = True         # arm stop-losses (False = TP-limit depth only, the stabiliser)
    tp_sig: int = 0                 # TP clustering (HANDOFF-v4 §6.1, Osler 2003): snap TP limit prices
                                    # to this many SIGNIFICANT FIGURES (0 = off). Scale-covariant by
                                    # construction (sig figs are relative), unlike an absolute grid.
                                    # Clusters the DEPTH onto discrete levels; the space between levels
                                    # is empty, and a gap is what a jump is.
    tp_sig_hier: bool = False       # hierarchy of roundness (Osler: 00 clusters beat 50): per-agent k
                                    # by id — 20% k=1, 40% k=2, 30% k=3, 10% unsnapped. Self-similar
                                    # grid; the second-order §6.1 prediction is that this preserves
                                    # scale-freeness where a single k cannot. Overrides tp_sig>0 arms
                                    # only in WHO snaps; requires tp_sig ignored when set.
    close_mode: str = "home"        # what an exit PROMISES (the symmetry fix, v4).
                                    # DEFAULT FLIPPED 2026-07-15: "home" is the symmetric null
                                    # baseline (HANDOFF-v4 §5); "quantity" is the named treatment
                                    # (squeezes, stranding, cover-drift). REFERENCE.md re-baselined
                                    # on the same date; the old quantity targets are retired.
                                    # "quantity" = both tribes close by re-trading a fixed BTC
                                    #              quantity (v3 behaviour, bit-identical). Short's
                                    #              buyback cost is unbounded -> stranding.
                                    # "home"     = each tribe closes by delivering the quantity it
                                    #              HOLDS from the entry: long sells its BTC, short
                                    #              spends its entry EUR proceeds (a spend order).
                                    #              Self-funded both sides; losses land in the home
                                    #              currency, bounded at 100%. Swap-covariant.
    sl_mode: str = "market"         # SL close execution discipline (the stranding fix):
                                    # "market" = v2 behaviour, bit-identical: cover joins the tick's
                                    #            market flow, walks the book, re-fires all-in each tick
                                    #            (absorbing stranding: EUR burned at cascade prices)
                                    # "limit"  = stop-limit: SL fires a reduce-only LIMIT at the stop
                                    #            level; fills what crosses, RESTS the remainder. No
                                    #            book-walking cascade, no EUR burn while waiting.
                                    # "wait"   = market cover only when the FULL cover is affordable
                                    #            at the current price; otherwise spend nothing this tick.
    entry_mode: str = "rest"         # how ENTRIES meet the market (v5 pure-CLOB switch):
                                    # "ioc"  = current behaviour, bit-identical: balanced entry flow
                                    #          crosses at p_prev impact-free (the auction vestige);
                                    #          the net imbalance walks the book; residuals VANISH.
                                    # "rest" = no auction. Every entry is a limit at the last price:
                                    #          fills what crosses, RESTS the remainder as real depth
                                    #          (the first passive orders that are not winners waiting).
                                    #          One resting entry per agent; each clock-fire while flat
                                    #          cancels-and-replaces it at the live price, so staleness
                                    #          is bounded by the agent's own period d/c and W stays
                                    #          vestigial. SL closes are market orders in both modes.
    hold_fires_close: bool = True   # impatience: the pressure clock also runs while HOLDING, and a
                                    # fire while in-position exits at market. One clock, two roles:
                                    # opens you when flat, closes you when stale (timescale = the
                                    # agent's own period d/c; no new parameter, scale-covariant).
                                    # This is unconditional-in-market-state aggression distributed
                                    # into every agent — the decentralised alternative to the house
                                    # maker for keeping a pure CLOB alive (see HANDOFF_clob.md):
                                    # without it, entry_mode="rest" converges to the all-holding
                                    # absorbing state at ANY population size.
    stall_T: int = 0                # liveness detector: stop the run if no trade has printed for this
                                    # many ticks (0 = off). Detects the CLOB absorbing states (Class 1/2,
                                    # HANDOFF-master par 4.7) instead of burning dead ticks; stopped_reason
                                    # names the stall. Detection, not prevention -- the freeze is a theorem.
    exit_btc_exact: bool = False    # home-mode short exits: False (default) = SPEND orders (the flip-
                                    # channel seed, par 4.9). True = BTC-EXACT exits (size=|pos.b|).
                                    # Measured: flips -96%; direction flips to 5/5 UP, +3.5 +/- 0.14.
    recycle: bool = True        # False = each agent opens at most once (no re-entry)
    x_accounting: bool = True   # True = size/PnL/exits in geometric-mean units X (1 X = p^-.5 EUR = p^.5 BTC); size = (W_X/q)/sqrt(p), identical both tribes
    symmetric_sizing: bool = False  # True = long open size price-independent (/x_0 not /p) to test drift
    frozen_sizing: bool = False     # True = open size fixed at f*K0/q (no wealth feedback) to test drift
    invariant_sizing: bool = False  # True = symmetric sizing (f*K0/q)*(x_0/p)^sizing_power, both tribes
    sizing_power: float = 0.5       # exponent in invariant sizing; 0.5 = exact numeraire-covariant p^(-1/2).
                                    # (~0.4 was the empirically drift-centering value in earlier calibration runs;
                                    # the committed default is the principled 0.5, not the calibrated 0.4)
    mirror: bool = False            # True = x->1/x mirror world: move the 1/p conversion to the BTC-home tribe
    symmetric_solvency: bool = True # True = clamp SELLs by BTC held, mirroring the EUR-spend clamp on BUYs
    log_thresholds: bool = True    # True = log-symmetric TP/SL bands x*e^{+-tp} (kills percentage gauge drift)
    # ── sizing-convention mix + evolution (§3f: no neutral convention exists;
    #    symmetry is constructed at the population level, or discovered by it) ──
    conv_mode: str = "legacy"       # "legacy" = the flags above behave exactly as before (bit-identical)
                                    # "mixed"  = per-agent trait conv_live: True = convert at the LIVE price
                                    #            (long: eur/(q*p); short: (btc/q)*(x_0/p)) — the tilt that bled
                                    #            in default/mirror respectively. False = convert at x_0 (no
                                    #            live-price factor). Overrides mirror/frozen/invariant sizing.
    conv_mix: float = 0.5           # init fraction of live-converters per tribe (0.5 = the 50/50 blend)
    conv_mix_long: Optional[float] = None    # per-tribe override of conv_mix (None = use conv_mix)
    conv_mix_short: Optional[float] = None   # the 2-D convention square: (1,0)=legacy corner, (0,1)=mirror corner
    evolve: bool = False            # imitation dynamics on conv_live (requires conv_mode="mixed")
    evolve_every: int = 2000        # epoch length in ticks (fitness window; must be >> position lifetime)
    evolve_frac: float = 0.2        # fraction of each tribe revising per epoch
    evolve_mutate: float = 0.02     # per-revision probability of a random flip (keeps both conventions alive)
    epsilon: Optional[float] = None  # bankruptcy threshold in EUR terms; computed 0.01*x_min if None
    T: int = 100_000             # maximum number of ticks (active-substrate baseline horizon)
    seed: Optional[int] = 42    # global RNG seed; None = fresh random run each time

    # ── house (actor, durable) ────────────────────────────────────────────────
    house_reserve_frac: float = 0.1   # house starting capital as a fraction of K, split 50/50 EUR/BTC at x_0
    #   bailout policy (optional; default OFF — agents self-rescue once positions+TP/SL exist):
    house_bailout: bool = False       # swap compositionally-stuck agents back toward the f split at p_int
    bailout_floor_frac: float = 0.1   # trigger: rescue when home_fraction < bailout_floor_frac * f
    bailout_before_bankruptcy: bool = False  # True: rescue BEFORE the death check

    # ── transitional — RETIRES when positions + TP/SL land (Phase 2) ──────────
    bankruptcy_price: str = "x_0"     # death test valuation: "x_0" (real capital) | "p_int" (instantaneous mark)
    #   -> superseded by the stop-loss exit
    baseline_metric: str = "x_min"    # all-in/fractional regime split: "x_min" | "K0_min"
    #   -> superseded by position sizing

    def __post_init__(self) -> None:
        if self.x_min is None:
            self.x_min = self.K / (self.n * 10)
        if self.epsilon is None:
            self.epsilon = 0.01 * self.x_min
        self.validate()

    def validate(self) -> None:
        """Fail loudly on nonsensical configuration before a run starts."""
        checks = {
            "n >= 1": self.n >= 1,
            "K > 0": self.K > 0,
            "x_0 > 0": self.x_0 > 0,
            "0 < f <= 1": 0.0 < self.f <= 1.0,
            "alpha > 1 (finite-mean Pareto)": self.alpha > 1.0,
            "capital_dist in {pareto,normal}": self.capital_dist in ("pareto", "normal"),
            "capital_cv > 0": self.capital_cv > 0,
            "0 < capital_floor < 1": 0.0 < self.capital_floor < 1.0,
            "clock_beta >= 0": self.clock_beta >= 0.0,
            "x_min > 0": self.x_min is not None and self.x_min > 0,
            "c > 0": self.c > 0,
            "q >= 1": self.q >= 1,
            "W >= 1": self.W >= 1,
            "tp > 0": self.tp > 0,
            "tp_sig >= 0": self.tp_sig >= 0,
            "sl_mode in {market,limit,wait}": self.sl_mode in ("market", "limit", "wait"),
            "close_mode in {quantity,home}": self.close_mode in ("quantity", "home"),
            "entry_mode in {ioc,rest}": self.entry_mode in ("ioc", "rest"),
            "close_mode=home requires sl_mode=market": self.close_mode != "home" or self.sl_mode == "market",
            "sl > 0": self.sl > 0,
            "epsilon >= 0": self.epsilon is not None and self.epsilon >= 0,
            "T >= 1": self.T >= 1,
            "conv_mode in {legacy,mixed}": self.conv_mode in ("legacy", "mixed"),
            "0 <= conv_mix <= 1": 0.0 <= self.conv_mix <= 1.0,
            "evolve requires mixed": (not self.evolve) or self.conv_mode == "mixed",
            "evolve_every >= 1": self.evolve_every >= 1,
            "0 < evolve_frac <= 1": 0.0 < self.evolve_frac <= 1.0,
            "0 <= evolve_mutate < 1": 0.0 <= self.evolve_mutate < 1.0,
            "house_reserve_frac >= 0": self.house_reserve_frac >= 0,
            "0 < bailout_floor_frac < 1": 0.0 < self.bailout_floor_frac < 1.0,
            "bankruptcy_price in {p_int,x_0}": self.bankruptcy_price in ("p_int", "x_0"),
            "baseline_metric in {x_min,K0_min}": self.baseline_metric in ("x_min", "K0_min"),
        }
        bad = [name for name, ok in checks.items() if not ok]
        if bad:
            raise ValueError("Invalid Config: " + "; ".join(bad))

    # ── convenience read-outs ─────────────────────────────────────────────────
    @property
    def total_agents(self) -> int:
        return 2 * self.n

    @property
    def smallest_fire_period(self) -> float:
        """Ticks between fires for the smallest agent: D_BASE / c."""
        return D_BASE / self.c

    def summary(self) -> str:
        sizing = ("X-accounting (geometric-mean)" if self.x_accounting else
                  "invariant p^-%g" % self.sizing_power if self.invariant_sizing else
                  "frozen (K0)" if self.frozen_sizing else
                  "symmetric (/x_0)" if self.symmetric_sizing else
                  "mirror" if self.mirror else "legacy (/p)")
        return (
            "Alpha Engine — resolved configuration\n"
            f"  engine            : close_mode={self.close_mode}  sl_mode={self.sl_mode}  entry_mode={self.entry_mode}  hold_fires_close={self.hold_fires_close}  conv_mode={self.conv_mode}\n"
            f"  population        : {self.total_agents} agents ({self.n} long / {self.n} short)\n"
            f"  total capital K   : {self.K:,.0f} EUR  (K/2 per side)\n"
            f"  x_0 / p_int(0)    : {self.x_0}\n"
            f"  f (home fraction) : {self.f}\n"
            f"  Pareto            : alpha={self.alpha}, x_min={self.x_min:,.2f}\n"
            f"  firing c          : {self.c}  -> smallest agent fires every {self.smallest_fire_period:,.0f} ticks\n"
            f"  trade             : home/q with q={self.q}\n"
            # ── the switches that DEFINE the model. Printed because omitting them
            #    let a silently-defaulted tp/sl hide behind a block that claimed
            #    otherwise: the run must state which mechanism actually ran.
            f"  exits             : tp={self.tp} sl={self.sl} "
            f"({'log-symmetric bands' if self.log_thresholds else 'ARITHMETIC bands (gauge drift!)'})"
            f"{'' if self.sl_enabled else '   [SL DISABLED]'}\n"
            f"  close_mode        : {self.close_mode}   sl_mode: {self.sl_mode}\n"
            f"  sizing            : {sizing}"
            f"{'   conv_mode=' + self.conv_mode if self.conv_mode != 'legacy' else ''}\n"
            f"  solvency clamp    : {'symmetric (both sides)' if self.symmetric_solvency else 'BUY-side only'}\n"
            f"  bankruptcy        : eps={self.epsilon:,.2f} EUR at {self.bankruptcy_price}\n"
            f"  house             : reserve_frac={self.house_reserve_frac}"
            f"{'  bailout ON' if self.house_bailout else '  bailout off'}\n"
            f"  horizon T         : {self.T:,} ticks   seed={self.seed}\n"
        )

    # ── serialization ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str = "config.json") -> str:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return path

    @classmethod
    def load(cls, path: str) -> "Config":
        with open(path) as f:
            return cls(**json.load(f))

    def to_python(self) -> str:
        args = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"Config({args})"


if __name__ == "__main__":
    cfg = Config()
    print(cfg.summary())
    cfg.save("config_demo.json")
    back = Config.load("config_demo.json")
    print("round-trip identical:", back.to_dict() == cfg.to_dict())
