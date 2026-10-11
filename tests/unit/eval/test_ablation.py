"""W5-08：OFAT 配置生成、McNemar、Holm、bootstrap、Wilson、可检测差距。"""

from __future__ import annotations

import pytest

from triwitness.eval.ablation import (
    bootstrap_ci,
    compare,
    holm,
    mcnemar,
    mde_independent,
    mde_paired,
    ofat,
    paired_diff_ci,
    render_rows,
    wilson,
)

BASE = {"name": "b", "harness": "configs/harness/baseline.yaml", "executor": {"model": "deepseek-flash",
        "thinking": True, "effort": "high"}, "attempts": 1}  # fmt: skip


def test_ofat_changes_one_factor_at_a_time() -> None:
    cfgs = ofat(BASE, {"context": {"none": {"harness": "configs/harness/no-context-mgmt.yaml"},
                                   "same": {"harness": "configs/harness/baseline.yaml"}},
                       "thinking": {"low": {"executor": {"effort": "low"}}}})  # fmt: skip
    assert [c.name for c in cfgs] == ["b", "b--context-none", "b--thinking-low"]  # 与基线相同的水平被跳过
    low = cfgs[2].config
    assert low["executor"] == {"model": "deepseek-flash", "thinking": True, "effort": "low"}
    assert low["harness"] == BASE["harness"] and BASE["executor"]["effort"] == "high"  # 基线没被改
    assert cfgs[1].factor == "context" and cfgs[0].factor is None


def test_mcnemar_exact_known_values() -> None:
    # 10 对：b = 6（A 过 B 不过）、c = 1 → 精确双侧 p = 2 × P(X ≤ 1 | n=7) = 2 × 8/128 = 0.125
    a = [True] * 6 + [False] + [True, False, True]
    b = [False] * 6 + [True] + [True, False, True]
    t = mcnemar(a, b)
    assert (t.b, t.c, t.n_eff, t.n) == (6, 1, 7, 10) and t.p_exact == pytest.approx(0.125)
    assert t.chi2_cc == pytest.approx((5 - 1) ** 2 / 7, abs=1e-3)
    assert mcnemar([True, False], [True, False]).p_exact == 1.0
    with pytest.raises(ValueError):
        mcnemar([True], [True, False])


def test_holm_adjustment() -> None:
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert holm([0.5, 0.9]) == [1.0, 1.0]
    assert holm([]) == []


def test_bootstrap_reproducible_and_brackets_mean() -> None:
    xs = [True] * 12 + [False] * 3
    ci = bootstrap_ci(xs, n=4000)
    assert ci == bootstrap_ci(xs, n=4000) and ci is not None
    assert ci[0] < 0.8 < ci[1] and ci[0] > 0.5 and ci[1] <= 1.0
    d = paired_diff_ci([True] * 10, [True] * 7 + [False] * 3, n=4000)
    assert d is not None and d[1] <= 0 and d[0] < -0.1
    assert bootstrap_ci([]) is None


def test_wilson_and_mde() -> None:
    lo, hi = wilson(12, 15)
    assert 0.54 < lo < 0.56 and 0.92 < hi < 0.94
    assert mde_independent(100) == pytest.approx(0.198, abs=0.002)  # n=100 → 约 20pp
    assert mde_paired(15, discordant=0.2) > 0.3  # dev 15 题只能看出很大的差距


def test_compare_pairs_on_common_tasks_and_holm() -> None:
    tasks = [f"t{i}" for i in range(20)]
    base = {t: i < 10 for i, t in enumerate(tasks)}
    better = {t: i < 19 for i, t in enumerate(tasks)}
    same = dict(base) | {"extra": True}  # 多出来的任务不参与配对
    rows = compare({"base": base, "better": better, "same": same}, "base", costs={"base": 1.0})
    r = {x.config: x for x in rows}
    assert r["better"].test is not None and r["better"].test.c == 9 and r["better"].diff == pytest.approx(0.45)
    assert r["better"].p_holm is not None and r["better"].verdict() == "更好"
    assert r["same"].n == 20 and r["same"].verdict() == "无显著差异" and r["base"].verdict() == "基线"
    md = render_rows(rows)
    assert "| better | 19/20 |" in md and "McNemar" in md
