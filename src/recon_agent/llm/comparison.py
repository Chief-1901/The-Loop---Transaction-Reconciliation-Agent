# src/recon_agent/llm/comparison.py
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from evals.scenarios.base import ScenarioResult


@dataclass
class ComparisonReport:
    observed_delta: float       # A_pass_rate - B_pass_rate
    ci_lower: float
    ci_upper: float
    p_value: float
    config_a_pass: float
    config_b_pass: float
    n: int


def compare_configs(
    config_a_results: list[ScenarioResult],
    config_b_results: list[ScenarioResult],
    n_resamples: int = 10_000,
    seed: int = 42,
) -> ComparisonReport:
    """Paired bootstrap. Assumes same scenarios in same order."""
    pairs = [
        (1 if a.passed else 0, 1 if b.passed else 0)
        for a, b in zip(config_a_results, config_b_results)
    ]
    n = len(pairs)
    if n == 0:
        return ComparisonReport(0, 0, 0, 1.0, 0, 0, 0)

    arr = np.array(pairs, dtype=float)
    observed = float(arr[:, 0].mean() - arr[:, 1].mean())

    rng = np.random.default_rng(seed)
    deltas = np.zeros(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        sample = arr[idx]
        deltas[i] = sample[:, 0].mean() - sample[:, 1].mean()

    ci_lower = float(np.quantile(deltas, 0.025))
    ci_upper = float(np.quantile(deltas, 0.975))
    # Two-sided p-value under H0 that the populations are interchangeable.
    centered = deltas - deltas.mean()
    p_value = float((np.abs(centered) >= abs(observed)).mean())

    return ComparisonReport(
        observed_delta=observed,
        ci_lower=ci_lower, ci_upper=ci_upper, p_value=p_value,
        config_a_pass=float(arr[:, 0].mean()),
        config_b_pass=float(arr[:, 1].mean()),
        n=n,
    )
