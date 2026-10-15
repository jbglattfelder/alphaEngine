"""Tests for the venue wrapper. Run:  python -m pytest venue/tests -q"""

from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(os.path.dirname(HERE), "py")
ROOT = os.path.dirname(os.path.dirname(HERE))           # simulation_mvp.py lives here
sys.path.insert(0, ROOT)
sys.path.insert(0, PY)

from simulation_mvp import Config, Simulation  # noqa: E402
from venue_wrapper import (USER_ID, X0, PaperPnL, Venue, VenueSim,  # noqa: E402
                           make_config)


def _frozen_hashes() -> dict[str, str]:
    out = {}
    with open(os.path.join(os.path.dirname(HERE), "FROZEN.sha256")) as f:
        for line in f:
            h, name = line.split()
            out[name] = h
    return out


def test_engine_is_byte_identical_to_the_freeze():
    for name, h in _frozen_hashes().items():
        with open(os.path.join(ROOT, name), "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == h, name


@pytest.mark.parametrize("arm", ["NNNN", "PFCF"])
def test_idle_human_leaves_the_engine_bit_identical(arm):
    """With an idle human (even holding coins) the market is the engine's own run."""
    cfg = make_config(n=50, K=1e6, tp=0.01, sl=0.01, c=0.004, q=8, seed=9, arm=arm)
    ref = Simulation(cfg)
    for t in range(1, 1501):
        ref.step(t)
    v = Venue(n=50, arm=arm, user_eur=10_000, user_rcc=100)
    v.step(1500)
    assert np.array_equal(np.asarray(ref.rec_price), np.asarray(v.sim.rec_price))
    assert ref._next_trade_id == v.sim._next_trade_id


def test_trim_keeps_the_run_identical():
    cfg = make_config(n=30, K=1e6, tp=0.01, sl=0.01, c=0.004, q=8, seed=3, arm="NNNN")
    ref = Simulation(cfg)
    prices = []
    for t in range(1, 2001):
        ref.step(t)
        prices.append(ref.p)
    v = Venue(n=30, seed=3, arm="NNNN")
    v.TRIM_EVERY = 250
    got = []
    for _ in range(20):
        got += [p for _, p in v.step(100)["ticks"]]
    assert got == prices


def _active_venue(seed=9, arm="NNNN", n=80):
    v = Venue(n=n, seed=seed, arm=arm, user_eur=40_000, user_rcc=400)
    v.step(200)
    rng = np.random.default_rng(seed)
    for k in range(60):
        p = v.sim.p
        r = rng.random()
        if r < 0.25:
            v.place("buy", "market", qty=float(rng.uniform(0.5, 5)))
        elif r < 0.5:
            v.place("sell", "market", qty=float(rng.uniform(0.5, 5)))
        elif r < 0.7:
            v.place("buy", "limit", qty=float(rng.uniform(1, 8)),
                    price=p * float(rng.uniform(0.99, 1.003)))
        elif r < 0.9:
            v.place("sell", "limit", qty=float(rng.uniform(1, 8)),
                    price=p * float(rng.uniform(0.997, 1.01)))
        else:
            oo = v.open_orders()
            if oo:
                v.cancel(oo[0]["id"])
        v.step(25)
    return v


@pytest.mark.parametrize("arm", ["NNNN", "PFCF"])
def test_closed_market_zero_sum_and_solvency(arm):
    v = _active_venue(arm=arm)
    sim = v.sim
    # conservation over agents + human (also asserted by the engine every tick)
    eur = sum(a.eur for a in sim.agents) + sim.user.eur
    btc = sum(a.btc for a in sim.agents) + sim.user.btc
    assert abs(eur - sim._grand_eur0) < 1e-6 * sim._grand_eur0
    assert abs(btc - sim._grand_btc0) < 1e-6 * sim._grand_btc0
    # zero-sum PnL: agents' engine PnL + the human's Eq. 9b
    p = sim.p
    tot = sum(a.total_pnl(p) for a in sim.agents) + sim.pnl.total_q(p)
    assert abs(tot) < 1e-6 * sim.cfg.K
    # the human's ledger closes to the wallet
    assert abs(sim.pnl.B + sim.pnl.b_tot - sim.user.btc) < 1e-9
    assert abs(sim.pnl.Q + sim.pnl.q_tot - sim.user.eur) < 1e-6
    # spot only
    assert sim.user.eur > -1e-9 and sim.user.btc > -1e-12
    le, lr = sim.locked()
    assert le <= sim.user.eur + 1e-9 and lr <= sim.user.btc + 1e-12
    # the human traded both as taker and as maker
    assert sim.pnl.n_fills > 0


def test_agents_hit_the_humans_resting_order():
    v = Venue(n=80, seed=9, arm="NNNN", user_eur=50_000, user_rcc=0)
    v.step(200)
    r = v.place("buy", "limit", qty=10, price=v.sim.p * 0.999)
    oid = r["order"]["id"]
    fills = []
    for _ in range(40):
        fills += v.step(25)["fills"]
    mine = [f for f in fills if f["order"] == oid]
    assert mine and all(f["role"] == "maker" for f in mine)
    assert all(f["counterparty"] != USER_ID for f in mine)
    uo = v.sim.user_orders[oid]
    assert abs(uo.filled - sum(f["size"] for f in mine)) < 1e-12


def test_limit_buy_is_quantity_not_notional():
    """A crossing limit buy fills exactly the asked RCC (the book itself
    denominates bids in EUR; the wrapper converts)."""
    v = Venue(n=80, seed=9, arm="NNNN", user_eur=200_000, user_rcc=0)
    v.step(300)
    qty = 3.0
    r = v.place("buy", "limit", qty=qty, price=v.sim.p * 1.02)
    o = r["order"]
    assert abs(o["filled"] + o["remaining"] - qty) < 1e-9
    assert abs(v.sim.user.btc - o["filled"]) < 1e-12


def test_spot_only_rejections_and_locking():
    v = Venue(n=50, seed=9, arm="NNNN", user_eur=1_000, user_rcc=1)
    v.step(100)
    assert v.place("sell", "market", qty=2)["order"]["status"] == "rejected"
    assert v.place("buy", "limit", qty=100, price=50)["order"]["status"] == "rejected"
    r = v.place("buy", "limit", qty=9, price=100)          # locks 900 EUR
    assert r["order"]["status"] in ("open", "partial", "filled")
    assert v.place("buy", "limit", qty=2, price=60)["order"]["status"] == "rejected"
    if r["order"]["status"] != "filled":
        v.cancel(r["order"]["id"])
        assert v.sim.locked()[0] == 0.0


def test_cancel():
    v = Venue(n=50, seed=9, arm="NNNN", user_eur=10_000, user_rcc=10)
    v.step(100)
    r = v.place("sell", "limit", qty=5, price=v.sim.p * 1.5)
    oid = r["order"]["id"]
    assert any(o["id"] == oid for o in v.open_orders())
    v.cancel(oid)
    assert not v.open_orders()
    assert v.sim.user_orders[oid].status == "cancelled"
    assert all(o.agent_id != USER_ID for o in v.sim.book.asks)


def test_allocation_cap():
    with pytest.raises(ValueError):
        Venue(n=10, K=1e6, user_eur=400_000, user_rcc=3_600)   # 760k > 750k
    Venue(n=10, K=1e6, user_eur=375_000, user_rcc=3_750)        # exactly 75 %


def test_paper_pnl_worked_example():
    """arXiv:2411.14068's SOL/USDT example, with the spread: every row of the
    p^b, p^q (Eqs. 3, 9) and W^q (Eq. 8b, B = 500, Q = 75,000) columns."""
    L = PaperPnL(B=500.0, Q=75_000.0)
    rows = [  # u, traded x, opposite x', p^b, p^q, W^q
        (+5, 170.00, 169.75, -0.007363, -1.25, 159_873.75),
        (+10, 175.00, 174.75, 0.121602, 21.25, 162_396.25),
        (-20, 180.00, 180.25, 0.547850, 98.75, 165_223.75),
        (+5, 160.00, 159.75, 1.25, 200.00, 155_200.00),
        (+12, 165.00, 164.75, 1.195751, 197.00, 157_572.00),
        (-12, 170.00, 170.25, 1.527165, 260.00, 160_385.00),
    ]
    for u, x, xo, pb, pq, wq in rows:
        L.fill(u, x)
        bid, ask = (xo, x) if u > 0 else (x, xo)     # buys trade at the ask
        xp = L.x_prime(last=x, bid=bid, ask=ask)
        assert abs(L.total_b(xp) - pb) < 1e-6, (u, x)   # the table truncates at 6 dp
        assert abs(L.total_q(xp) - pq) < 1e-9, (u, x)
        assert abs(L.wealth_q(xp) - wq) < 1e-6, (u, x)
    assert L.b == 0.0 and abs(L.realised - 260.0) < 1e-9
    v = L.view(last=170.0, bid=170.0, ask=170.25)
    assert abs(v["perf"] - 1.527165 / (500 + 75_000 / X0)) < 1e-6   # Sec. 3, the venue x0
    assert v["unrealised"] == 0.0


def test_paper_pnl_split_adds_up():
    L = PaperPnL(B=1.0, Q=100.0)
    L.fill(+2, 100.0)
    assert L.avg_price() == 100.0
    L.fill(-1, 110.0)                 # partial: stays open, nothing banked
    assert L.realised == 0.0 and abs(L.unrealised(110.0) - 20.0) < 1e-12
    L.fill(-3, 120.0)                 # closes (+30 banked) and flips short 2 @ 120
    assert abs(L.realised - 30.0) < 1e-12   # 10 (partial) + 20 (close)
    assert L.b == -2.0 and L.avg_price() == 120.0
    for x in (90.0, 120.0, 150.0):
        assert abs(L.realised + L.unrealised(x) - L.total_q(x)) < 1e-9
