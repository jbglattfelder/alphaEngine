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
        got += [row[1] for row in v.step(100)["ticks"]]
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


def test_tick_volume_adds_up_to_session_volume():
    v = Venue(n=60, seed=4, arm="NNNN", user_eur=20_000, user_rcc=200)
    vol = sum(row[2] for row in v.step(300)["ticks"])
    v.place("buy", "market", qty=2.0)                 # between ticks: lands in the next bar
    vol += sum(row[2] for row in v.step(300)["ticks"])
    assert abs(vol - v.sim.volume) < 1e-9 * max(1.0, v.sim.volume)


def test_reference_tape_is_the_engines():
    """The committed n=2 reference (used by e2e/tape.spec.js) is a fresh run
    of the bare engine, so the GUI is compared with the engine itself."""
    import json
    sys.path.insert(0, HERE)
    import reference_tape
    with open(reference_tape.PATH) as f:
        committed = json.load(f)
    assert committed == json.loads(json.dumps(reference_tape.build()))


def test_wrapper_reproduces_the_reference_tape():
    """The venue (wrapper + idle human with zero allocation) prints the same tape."""
    import hashlib, json
    sys.path.insert(0, HERE)
    import reference_tape
    with open(reference_tape.PATH) as f:
        ref = json.load(f)
    for c in ref["cases"]:
        v = Venue(n=c["n"], seed=c["seed"], arm=c["arm"])
        prices = [X0] + [row[1] for row in v.step(c["T"])["ticks"]]
        hexes = "".join(reference_tape.fhex(p) for p in prices)
        assert hashlib.sha256(hexes.encode()).hexdigest() == c["sha256"], c["arm"]


def test_position_entry_price_and_side():
    L = PaperPnL(B=1.0, Q=100.0)
    assert L.view(100.0)["side"] is None
    L.fill(+2, 100.0, tick=5)
    L.fill(+2, 110.0, tick=6)                       # add: entry stays, x-bar moves
    v = L.view(120.0, bid=119.0, ask=121.0)
    assert (v["side"], v["size"], v["entry_price"], v["opened_tick"]) == ("long", 4.0, 100.0, 5)
    assert v["avg_price"] == 105.0 and v["value"] == 4 * 119.0
    L.fill(-1, 120.0, tick=7)                       # reduce: still the same position
    assert L.view(120.0)["entry_price"] == 100.0
    L.fill(-5, 130.0, tick=8)                       # flip: short 2 opened at 130
    v = L.view(125.0, bid=124.0, ask=126.0)
    assert (v["side"], v["size"], v["entry_price"], v["opened_tick"]) == ("short", 2.0, 130.0, 8)
    L.fill(+2, 125.0, tick=9)                       # close
    v = L.view(125.0)
    assert (v["side"], v["entry_price"], v["opened_tick"]) == (None, None, None)


def _lots(v):
    return {p["id"]: p for p in v.positions()}


def test_every_order_opens_its_own_position():
    v = Venue(n=80, seed=9, arm="NNNN", user_eur=200_000, user_rcc=1_000)
    v.step(300)
    v.place("buy", "market", qty=2)
    v.place("buy", "market", qty=3)
    v.place("sell", "market", qty=1)                  # not netted: a short of its own
    P = v.positions()
    assert [(p["side"], round(p["size"], 9)) for p in P] == [("long", 2), ("long", 3), ("short", 1)]
    assert all(p["entry_price"] > 0 and p["order"] for p in P)


def test_partial_fills_grow_one_position():
    v = Venue(n=80, seed=9, arm="NNNN", user_eur=200_000, user_rcc=0)
    v.step(200)
    r = v.place("buy", "limit", qty=20, price=v.sim.p * 0.999)
    oid = r["order"]["id"]
    for _ in range(60):
        v.step(10)
        if v.sim.user_orders[oid].status == "filled":
            break
    uo = v.sim.user_orders[oid]
    mine = [p for p in v.positions() if p["order"] == oid]
    assert uo.filled > 0 and len(mine) == 1             # many fills, one position
    assert abs(mine[0]["size"] - uo.filled) < 1e-9
    assert abs(mine[0]["avg_price"] - uo.notional / uo.filled) < 1e-9


def test_position_actions_touch_only_their_position():
    v = Venue(n=80, seed=9, arm="NNNN", user_eur=200_000, user_rcc=1_000)
    v.step(300)
    v.place("buy", "market", qty=2)
    v.place("buy", "market", qty=4)
    a, b = sorted(_lots(v))
    v.place("buy", "market", qty=1, pos_id=a)           # Increase a
    assert abs(_lots(v)[a]["size"] - 3) < 1e-9 and len(v.positions()) == 2
    v.place("sell", "market", qty=1.5, pos_id=b)        # Decrease b
    L = _lots(v)
    assert abs(L[b]["size"] - 2.5) < 1e-9 and abs(L[a]["size"] - 3) < 1e-9
    assert L[b]["realised"] != 0.0
    v.place("sell", "market", qty=3, pos_id=a)          # Close a
    assert set(_lots(v)) == {b}
    v.place("sell", "market", qty=4, pos_id=b)          # Decrease b past zero: short 1.5
    P = v.positions()
    assert len(P) == 1 and P[0]["side"] == "short" and abs(P[0]["size"] - 1.5) < 1e-9 and P[0]["id"] not in (a, b)


def test_positions_add_up_to_the_account():
    """At one price, the positions' realised + unrealised = the account's Eq. 9b."""
    v = Venue(n=80, seed=3, arm="PFCF", user_eur=200_000, user_rcc=1_000)
    v.step(200)
    rng = np.random.default_rng(1)
    for k in range(30):
        side = "buy" if rng.random() < 0.5 else "sell"
        pos = list(v.sim.lots) or [None]
        v.place(side, "market", qty=float(rng.uniform(0.2, 3)),
                pos_id=(pos[0] if rng.random() < 0.3 else None))
        v.step(20)
    x = v.sim.p
    lots = v.sim.lots_banked + sum(l.realised + x * l.b + l.q for l in v.sim.lots.values())
    assert abs(lots - v.sim.pnl.total_q(x)) < 1e-6
    total_lots_b = sum(l.b for l in v.sim.lots.values())
    assert abs(total_lots_b - v.sim.pnl.b_tot) < 1e-9          # positions hold exactly the net RCC
