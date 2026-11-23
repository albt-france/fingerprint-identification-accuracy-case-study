"""Small, tested statistics helpers used by findings.py, monitoring, the tools and the notebook.

Every function is plain NumPy / SciPy so that each number can be re-derived by hand (see docs/statistics_notes.md).
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion k / n. Stays inside [0, 1] and behaves well for small rates."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def cluster_bootstrap_rate(k_by_cluster: np.ndarray, n_by_cluster: np.ndarray, b: int = 1000, seed: int = 42,
                           level: float = 0.95) -> dict:
    """Percentile bootstrap of a ratio sum(k) / sum(n) that resamples CLUSTERS (visitors), not events.

    Events of one device are correlated (the same device tends to be misidentified again), so resampling events
    pretends we have more independent information than we do and gives intervals that are too narrow."""
    k = np.asarray(k_by_cluster, dtype=float)
    n = np.asarray(n_by_cluster, dtype=float)
    rng = np.random.default_rng(seed)
    c = len(k)
    reps = np.empty(b)
    for i in range(b):
        w = np.bincount(rng.integers(0, c, c), minlength=c)      # how many times each cluster is drawn
        reps[i] = (w * k).sum() / (w * n).sum()
    a = (1 - level) / 2
    return {"rate": k.sum() / n.sum(), "lo": float(np.quantile(reps, a)), "hi": float(np.quantile(reps, 1 - a)),
            "se": float(reps.std(ddof=1))}


def design_effect(k_by_cluster: np.ndarray, n_by_cluster: np.ndarray, b: int = 1000, seed: int = 42) -> float:
    """Variance of the clustered estimate / variance assuming independent events (1 = no clustering)."""
    k = np.asarray(k_by_cluster, dtype=float)
    n = np.asarray(n_by_cluster, dtype=float)
    p = k.sum() / n.sum()
    naive_var = p * (1 - p) / n.sum()
    se = cluster_bootstrap_rate(k, n, b=b, seed=seed)["se"]
    return float(se ** 2 / naive_var) if naive_var > 0 else float("nan")


def two_proportion_test(k1: float, n1: float, k2: float, n2: float, phi: float = 1.0) -> dict:
    """Is rate 2 different from rate 1? Pooled z-test with an over-dispersion factor phi (quasi-binomial).
    Returns the difference, its 95% interval, z and the two-sided p-value."""
    p1, p2 = k1 / n1, k2 / n2
    p = (k1 + k2) / (n1 + n2)
    se_pooled = np.sqrt(phi * p * (1 - p) * (1 / n1 + 1 / n2))
    z = (p2 - p1) / se_pooled if se_pooled > 0 else float("nan")
    se_diff = np.sqrt(phi * (p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2))
    return {"rate_a": p1, "rate_b": p2, "diff": p2 - p1, "diff_lo": p2 - p1 - 1.96 * se_diff, "diff_hi": p2 - p1 + 1.96 * se_diff,
            "relative_change": (p2 - p1) / p1 if p1 > 0 else float("nan"), "z": float(z), "p_value": float(2 * stats.norm.sf(abs(z)))}


def required_n(p0: float, delta: float, alpha: float = 0.05, power: float = 0.8, phi: float = 1.0) -> float:
    """Events needed IN EACH of two periods to detect an absolute change `delta` of a rate p0 (two-sided test).
        n = (z_{1-alpha/2} + z_{power})^2 * phi * 2 * p0 * (1 - p0) / delta^2"""
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return float((za + zb) ** 2 * phi * 2 * p0 * (1 - p0) / delta ** 2)


def mde(p0: float, n: float, alpha: float = 0.05, power: float = 0.8, phi: float = 1.0) -> float:
    """Minimal detectable absolute change of a rate p0 with n events in each of two periods (inverse of required_n)."""
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return float((za + zb) * np.sqrt(phi * 2 * p0 * (1 - p0) / n))


def direct_standardize(k: np.ndarray, n: np.ndarray, weights: np.ndarray) -> float:
    """Directly standardized rate: segment rates k/n weighted by a FIXED reference mix (weights sum to 1).
    A change of traffic mix cannot move it; only changes within segments can."""
    k, n, w = (np.asarray(x, dtype=float) for x in (k, n, weights))
    ok = n > 0
    return float((w[ok] * k[ok] / n[ok]).sum() / w[ok].sum())


def reliability_table(score: np.ndarray, is_fp: np.ndarray, bins: list[float]) -> list[dict]:
    """Calibration of a confidence score defined as 1 - P(false positive): per score bin, the mean score
    (= predicted precision) against the observed share of correct matches (1 - FP share)."""
    score, is_fp = np.asarray(score, float), np.asarray(is_fp, float)
    out = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        m = (score >= lo) & (score < hi) if hi < bins[-1] else (score >= lo) & (score <= hi)
        if m.sum() == 0:
            continue
        out.append({"bin_lo": lo, "bin_hi": hi, "n": int(m.sum()), "mean_score": float(score[m].mean()),
                    "observed_precision": float(1 - is_fp[m].mean())})
    return out


def expected_calibration_error(table: list[dict]) -> float:
    """ECE = sum over bins of (bin share) x |mean score - observed precision|."""
    n = sum(r["n"] for r in table)
    return float(sum(r["n"] / n * abs(r["mean_score"] - r["observed_precision"]) for r in table)) if n else float("nan")
