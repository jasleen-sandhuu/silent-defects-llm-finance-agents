"""Statistics used to design and read the study. Pure functions, no I/O.

Setting: N cases, K runs per case. Runs of one case are correlated (intra-class correlation rho),
so the information in N*K runs is less than N*K independent trials.

  Kish design effect         DEFF = 1 + (m - 1) * rho            (m = runs per case)
  Effective sample size      n_eff = n_runs / DEFF
  Variance of a mean         Var ~ p(1-p) / n_eff = p(1-p) * DEFF / (N*K)
  Best K for a fixed budget  minimise DEFF / (N*K) with N*K fixed -> as N grows K shrinks;
                             with rho -> 1 extra repeats add almost nothing, extra cases do.
  Zero events                exact one-sided upper bound  1 - alpha ** (1 / n_eff)  ("rule of three")
  Detectable difference      MDE ~ (z_{1-a} + z_{power}) * sqrt(2 p(1-p) / n_eff)   (one-sided)
"""
from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np

_N = NormalDist()


def design_effect(m: float, rho: float) -> float:
    rho = min(max(rho, 0.0), 1.0)
    return 1.0 + (m - 1.0) * rho


def n_eff(n_runs: float, m: float, rho: float) -> float:
    return n_runs / design_effect(m, rho)


def upper_bound_zero(n: float, alpha: float = 0.05) -> float:
    """Exact one-sided (1-alpha) upper confidence bound for a proportion after 0 events in n trials."""
    if n <= 0:
        return 1.0
    return 1.0 - alpha ** (1.0 / n)


def n_to_certify(s0: float, alpha: float = 0.05) -> int:
    """Independent trials with zero events needed to be (1-alpha) sure the rate is below s0."""
    return math.ceil(math.log(alpha) / math.log(1.0 - s0))


def clopper_pearson_upper(k: int, n: int, alpha: float = 0.05) -> float:
    """Exact one-sided upper bound for k events in n trials (bisection on the binomial tail)."""
    if n <= 0:
        return 1.0
    if k >= n:
        return 1.0

    def tail(p):  # P(X <= k | p)
        return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))

    lo, hi = k / n, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if tail(mid) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def mde(n_eff_each: float, p0: float = 0.1, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest true increase in a rate detectable (one-sided test, two groups of n_eff_each)."""
    z = _N.inv_cdf(1 - alpha) + _N.inv_cdf(power)
    return z * math.sqrt(2 * p0 * (1 - p0) / n_eff_each)


def cases_needed(delta: float, m: float, rho: float, p0: float = 0.1, alpha: float = 0.05,
                 power: float = 0.8, correct_share: float = 1.0) -> int:
    """Cases needed (each with m runs) to detect a rate increase of `delta` over p0."""
    z = _N.inv_cdf(1 - alpha) + _N.inv_cdf(power)
    n_eff_needed = 2 * p0 * (1 - p0) * (z / delta) ** 2
    runs = n_eff_needed * design_effect(m, rho) / correct_share
    return math.ceil(runs / m)


def best_k(budget_runs: int, rho: float, k_min: int = 2, k_max: int = 10):
    """K minimising DEFF/(N*K) subject to N*K = budget, K >= k_min (K=1 cannot measure repeat agreement)."""
    best = None
    for k in range(k_min, k_max + 1):
        v = design_effect(k, rho) / budget_runs  # same N*K for every k
        if best is None or v < best[1] - 1e-15:
            best = (k, v)
    k = best[0]
    return k, budget_runs // k


def holm(pvals: dict) -> dict:
    """Holm-Bonferroni adjusted p-values (controls the family-wise error rate)."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, adj, running = len(items), {}, 0.0
    for i, (name, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adj[name] = running
    return adj


def paired_bootstrap(counts: dict, base: str, reps: int = 10000, seed: int = 12345):
    """Paired cluster bootstrap over cases.

    counts[cond] = (n_silent, n_correct) arrays aligned on the SAME cases. One resampled set of
    case indices is applied to every condition, which preserves the pairing and removes
    between-case noise from the contrasts. Returns sigma draws and difference-vs-base draws.
    """
    rng = np.random.default_rng(seed)
    n = len(next(iter(counts.values()))[0])
    idx = rng.integers(0, n, size=(reps, n))
    sig = {}
    for c, (s, k) in counts.items():
        num, den = s[idx].sum(1), k[idx].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            sig[c] = np.where(den > 0, num / den, np.nan)
    diff = {c: sig[c] - sig[base] for c in counts if c != base}
    return sig, diff


def one_sided_p(draws: np.ndarray) -> float:
    """Bootstrap p-value for H1: effect > 0 (add-one so it is never exactly 0)."""
    d = draws[~np.isnan(draws)]
    return (1 + int((d <= 0).sum())) / (len(d) + 1)


def verdict(lower: float, upper: float, threshold: float) -> str:
    """Review-everything decision against the cost threshold c_h / (q c_e)."""
    if lower > threshold:
        return "justified"
    if upper < threshold:
        return "not justified"
    return "inconclusive"


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="design calculator")
    ap.add_argument("--rho", type=float, required=True, help="ICC of the defect/correct indicator within cases")
    ap.add_argument("--budget", type=int, default=200, help="runs per condition")
    ap.add_argument("--delta", type=float, default=0.15, help="sigma increase worth detecting")
    a = ap.parse_args()
    k, n = best_k(a.budget, a.rho)
    print(f"rho={a.rho:.2f} budget={a.budget}: best K={k}, cases={n}, DEFF={design_effect(k, a.rho):.2f}, "
          f"n_eff={n_eff(a.budget, k, a.rho):.1f}")
    for kk in (2, 3, 5):
        nn = a.budget // kk
        ne = n_eff(nn * kk, kk, a.rho)
        print(f"  K={kk} N={nn}: n_eff={ne:.1f}, zero-event 95% upper bound={upper_bound_zero(ne):.3f}, "
              f"MDE={mde(ne):.3f}")
    print(f"cases needed (K={k}) to detect +{a.delta:.2f}: {cases_needed(a.delta, k, a.rho)}")


if __name__ == "__main__":
    _cli()
