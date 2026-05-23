# tests/unit/test_comparison.py
from recon_agent.llm.comparison import compare_configs
from evals.scenarios.base import ScenarioResult


def _r(name: str, passed: bool) -> ScenarioResult:
    return ScenarioResult(name=name, passed=passed)


def test_compare_perfect_a_imperfect_b():
    a = [_r(f"s{i}", True) for i in range(12)]
    b = [_r(f"s{i}", True) for i in range(10)] + [_r("s10", False), _r("s11", False)]
    rep = compare_configs(a, b, n_resamples=2000)
    assert rep.observed_delta > 0
    assert rep.config_a_pass == 1.0
    assert rep.config_b_pass < 1.0
    assert rep.n == 12


def test_compare_identical_no_delta():
    a = [_r(f"s{i}", True) for i in range(10)]
    b = [_r(f"s{i}", True) for i in range(10)]
    rep = compare_configs(a, b, n_resamples=2000)
    assert rep.observed_delta == 0
