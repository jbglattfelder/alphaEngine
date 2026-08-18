"""
position.py — balance-sheet PnL accounting (Glattfelder & Houweling, 2024,
"Calculating Profits and Losses for Algorithmic Trading Strategies", arXiv:2411.14068).

Pair BTC/EUR: base b = BTC (the asset), quote q = EUR (the money), price x = p_int
(EUR per BTC). A Position is the running trade tally, independent of the actor's
starting endowment:

    buy  u base at x:  b += u,  q -= x*u
    sell u base     :  b -= u,  q += x*u   (u<0 in trade())
    =>  b_i = sum u_j        (net base acquired by trading)        Eq (1a)
        q_i = -sum x_j u_j   (net quote laid out, signed)          Eq (1b)

Average entry price   x_bar = -q/b                                  Eq (2)
PnL vs the no-trading benchmark (Eq 9), with no spread (x' = x = p):
        pnl_quote(p) = p*b + q     (EUR)                           Eq (9b)
        pnl_base(p)  = b + q/p     (BTC)                           Eq (9a)

Spread (bid/ask, the x' != x case and the b->0 closing nuance of Eq 3/10) is
deferred to the external-actors phase; with a single clearing price these reduce
to the expressions above, which are exact.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass
class Position:
    b: float = 0.0   # net base (BTC) acquired by trading
    q: float = 0.0   # net quote (EUR) laid out, signed (= -sum x*u)

    def trade(self, u: float, x: float) -> None:
        """u units of base at price x (u>0 buy, u<0 sell)."""
        self.b += u
        self.q -= x * u

    def apply_fill(self, eur_delta: float, btc_delta: float) -> None:
        """Engine fills already encode the deltas: eur_delta = -x*u, btc_delta = u."""
        self.b += btc_delta
        self.q += eur_delta

    @property
    def avg_price(self) -> float:
        return math.nan if self.b == 0 else -self.q / self.b

    def pnl_quote(self, p: float) -> float:   # EUR
        return p * self.b + self.q

    def pnl_base(self, p: float) -> float:    # BTC
        return math.nan if p == 0 else self.b + self.q / p

    def ret(self, p: float) -> float:
        """Signed return of the open position, for TP/SL. >0 = in profit for
        EITHER side (long profits when p>x̄, short when p<x̄). Scale-free:
            ret = pnl_quote / |q| = (p*b + q)/|q| = ±(p − x̄)/x̄.
        """
        return 0.0 if self.q == 0 else (p * self.b + self.q) / abs(self.q)


if __name__ == "__main__":
    # Verify the b/q tally and quote-PnL against the paper's SOL/USDT example.
    # (base=SOL, quote=USDT, price in USDT/SOL). Trades: buy at ask, sell at bid.
    trades = [(+5, 170.0), (+10, 175.0), (-20, 180.0), (+5, 160.0), (+12, 165.0), (-12, 170.0)]
    pos = Position()
    qs = []
    for u, x in trades:
        pos.trade(u, x)
        qs.append(pos.q)
    print("q after each trade:", [round(v, 2) for v in qs])
    print("q_6 (realized USDT profit):", round(pos.q, 6), " expected 260.0")
    # At the close (b=0), pnl_quote at the closing price = realized profit = q.
    print("pnl_quote @170 :", round(pos.pnl_quote(170.0), 6), " expected 260.0 (p^q_6)")
    print("pnl_base   @170 :", round(pos.pnl_base(170.0), 6), " ~1.527 (paper 1.527165; diff = spread, not modelled)")
    assert abs(pos.q - 260.0) < 1e-9, "q tally mismatch"
    assert abs(pos.pnl_quote(170.0) - 260.0) < 1e-9, "quote PnL mismatch"
    print("OK — balance-sheet tally matches the paper.")
