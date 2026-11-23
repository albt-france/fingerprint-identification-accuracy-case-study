"""Unit tests of src/metrics.py: known values computed by hand or from textbook formulas."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import metrics  # noqa: E402


def test_wilson_known_value():
    # 10 successes out of 100: Wilson 95% interval is about [0.0552, 0.1744]
    lo, hi = metrics.wilson(10, 100)
    assert lo == pytest.approx(0.0552, abs=1e-3)
    assert hi == pytest.approx(0.1744, abs=1e-3)


def test_wilson_zero_successes_stays_in_bounds():
    lo, hi = metrics.wilson(0, 50)
    assert lo == 0.0 and 0 < hi < 0.1


def test_wilson_empty():
    assert all(np.isnan(metrics.wilson(0, 0)))


def test_cluster_bootstrap_wider_than_naive_when_clustered():
    rng = np.random.default_rng(0)
    # 2,000 visitors with 30 events each; half of the visitors are "bad" devices with a high FP rate
    n = np.full(2000, 30)
    p_dev = np.where(rng.random(2000) < 0.5, 0.001, 0.08)
    k = rng.binomial(n, p_dev)
    res = metrics.cluster_bootstrap_rate(k, n, b=400, seed=1)
    p = k.sum() / n.sum()
    naive_half = 1.96 * np.sqrt(p * (1 - p) / n.sum())
    assert (res["hi"] - res["lo"]) / 2 > 1.2 * naive_half
    assert metrics.design_effect(k, n, b=400) > 1.3


def test_cluster_bootstrap_matches_naive_without_clustering():
    rng = np.random.default_rng(3)
    n = np.ones(20000, dtype=int)          # one event per visitor: clusters = events
    k = rng.binomial(n, 0.05)
    deff = metrics.design_effect(k, n, b=400)
    assert 0.8 < deff < 1.25


def test_required_n_and_mde_are_inverse():
    n = metrics.required_n(0.01, 0.002)
    assert metrics.mde(0.01, n) == pytest.approx(0.002, rel=1e-6)
    # textbook value: p0 = 1%, delta = 0.2 pt, alpha 5%, power 80% -> about 38,800 events per period
    assert n == pytest.approx(38_820, rel=0.01)


def test_overdispersion_increases_required_n():
    assert metrics.required_n(0.01, 0.002, phi=2.0) == pytest.approx(2 * metrics.required_n(0.01, 0.002))


def test_two_proportion_test_detects_real_change_only():
    big = metrics.two_proportion_test(100, 10000, 200, 10000)
    small = metrics.two_proportion_test(100, 10000, 105, 10000)
    assert big["p_value"] < 1e-6 and small["p_value"] > 0.5
    assert big["relative_change"] == pytest.approx(1.0)


def test_direct_standardization_removes_mix_effect():
    # two segments with constant rates (1% desktop, 3% mobile); the mix moves from 80/20 to 50/50
    rates = np.array([0.01, 0.03])
    w_ref = np.array([0.8, 0.2])
    before_n, after_n = np.array([8000, 2000]), np.array([5000, 5000])
    crude_before = (rates * before_n).sum() / before_n.sum()
    crude_after = (rates * after_n).sum() / after_n.sum()
    assert crude_after > crude_before * 1.3                        # the crude rate jumps (Simpson-type mix effect)
    std_before = metrics.direct_standardize(rates * before_n, before_n, w_ref)
    std_after = metrics.direct_standardize(rates * after_n, after_n, w_ref)
    assert std_before == pytest.approx(std_after)                   # the standardized rate does not move


def test_calibration_perfect_and_overconfident():
    rng = np.random.default_rng(5)
    risk = rng.uniform(0, 0.2, 200_000)
    is_fp = rng.random(200_000) < risk
    bins = [0.8, 0.85, 0.9, 0.95, 1.0]
    good = metrics.reliability_table(1 - risk, is_fp, bins)
    over = metrics.reliability_table(1 - 0.5 * risk, is_fp, bins)   # announces half of the real risk
    assert metrics.expected_calibration_error(good) < 0.005
    assert metrics.expected_calibration_error(over) > 0.03
