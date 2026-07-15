"""Validate dc_analysis against Brownian motion, where arXiv:2204.02682 Tbl.1 gives
the answers: N_hat ~ delta^-1.90, <omega> ~ delta^0.98, <omega-delta>_2 ~ delta^1.91,
<r(dt)>_2 ~ dt^1.00, and C^T ~= C^tau ~= sigma^2."""
import numpy as np
from dc_analysis import analyse
rng = np.random.default_rng(7)
SIG = 0.002
n = 400_000
p = 100.0 * np.exp(np.cumsum(rng.normal(0, SIG, n)) - 0.5*SIG**2*np.arange(n))
print("=== Brownian motion control (sigma = %.4g, so sigma^2 = %.4g) ===" % (SIG, SIG**2))
analyse(p, plot_path=None)
