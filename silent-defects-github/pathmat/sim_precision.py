#!/usr/bin/env python3
"""Scenario simulation of the company-clustered pooled-ratio estimator (for choosing N and K).

Per run: A~Bernoulli(p_A(case)), V~Bernoulli(p_V(case)), independent given the case, with
logit p_X(case) = logit(base_X) + sd_company*z_company + sd_case*z_case. Strata are ignored (one pooled
population). All inputs are ASSUMED scenarios, not estimates; replace them with pilot values
when a live pilot exists. Output: mean 95% interval width and coverage of the true pooled sigma.

  python sim_precision.py --companies 14 --n-cases 40 80 160 --k 1 3 5
"""
import argparse
import itertools

import numpy as np


def expit(x):
    return 1 / (1 + np.exp(-x))


def logit(p):
    return np.log(p / (1 - p))


def one(rng, G, N, K, pA, pV, sd_g, sd_c, B):
    comp = rng.integers(0, G, N)
    zg_a, zg_v = rng.normal(0, sd_g, G), rng.normal(0, sd_g, G)
    pa = expit(logit(pA) + zg_a[comp] + rng.normal(0, sd_c, N))
    pv = expit(logit(pV) + zg_v[comp] + rng.normal(0, sd_c, N))
    A = rng.random((N, K)) < pa[:, None]
    V = rng.random((N, K)) < pv[:, None]
    n_corr, n_sil = A.sum(1), (A & V).sum(1)
    # true pooled sigma for this realised population
    truth = (pa * pv).sum() / pa.sum()
    gs = np.unique(comp)
    gc = np.array([n_corr[comp == g].sum() for g in gs], float)
    gn = np.array([n_sil[comp == g].sum() for g in gs], float)
    idx = rng.integers(0, len(gs), (B, len(gs)))
    d = gc[idx].sum(1)
    ok = d > 0
    v = gn[idx].sum(1)[ok] / d[ok]
    lo, hi = np.percentile(v, [2.5, 97.5])
    return hi - lo, lo <= truth <= hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", type=int, default=14)
    ap.add_argument("--n-cases", type=int, nargs="+", default=[40, 80, 160])
    ap.add_argument("--k", type=int, nargs="+", default=[1, 3, 5])
    ap.add_argument("--p-correct", type=float, nargs="+", default=[0.8])
    ap.add_argument("--sigma", type=float, nargs="+", default=[0.1, 0.3])
    ap.add_argument("--sd-company", type=float, default=0.5)
    ap.add_argument("--sd-case", type=float, default=1.0)
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    print(f"G={a.companies} companies; sd_company={a.sd_company}, sd_case={a.sd_case} (logit scale); "
          f"{a.reps} sims x {a.boot} bootstrap reps. Inputs are assumed scenarios.")
    print("p_correct  sigma(true)  N  K  mean_width(pp)  coverage")
    for pA, pV, N, K in itertools.product(a.p_correct, a.sigma, a.n_cases, a.k):
        res = [one(rng, a.companies, N, K, pA, pV, a.sd_company, a.sd_case, a.boot) for _ in range(a.reps)]
        w = np.mean([r[0] for r in res]) * 100
        cov = np.mean([r[1] for r in res])
        print(f"{pA:9.2f}  {pV:11.2f}  {N:3d} {K:2d}  {w:13.1f}  {cov:8.2f}")


if __name__ == "__main__":
    main()
