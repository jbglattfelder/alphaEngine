"""Guards cross-machine bit-reproducibility of the initial capital draw.

The tick loop is + - * / and comparisons: IEEE-754 pins those exactly.
The ONLY transcendental is the Pareto inverse-CDF at init, so it uses `decimal`
(software, specified semantics) rather than libm pow (ARM/x86 differ by 1 ulp).
The model is chaotic: 1 ulp in one K0 rewrites the entire history.
If this test fails, someone reintroduced a platform-dependent op at init.
"""
import hashlib
from config import Config
from agents import Population


def test_k0_bit_exact():
    k0 = [float(a.K0) for a in Population(Config(seed=42)).agents]
    assert k0[0].hex() == "0x1.0108deb557290p+12"
    assert k0[-1].hex() == "0x1.4d8420d8e0779p+11"
    assert hashlib.sha1(repr(k0).encode()).hexdigest()[:16] == "25029ccde7c44d03"


def test_capital_conserved():
    cfg = Config(seed=42)
    pop = Population(cfg)
    assert abs(sum(a.K0 for a in pop.agents) - cfg.K) < 1e-6
