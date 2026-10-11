"""消融实验的配置生成与统计（W5-08；04 §6.2 统计方法、§6.3）。评审者消融（scripts/reviewer_ablation.py）也用这里的统计。

- `ofat()`：基线 + 一次只改一个因素（One-Factor-At-a-Time），每个水平是对 RunConfig 的覆盖（可嵌套）。
- `mcnemar()`：配对二值结果的 McNemar 检验（精确二项 p 值；n_eff = 不一致对数）。
- `holm()`：Holm–Bonferroni 多重比较校正。
- `bootstrap_ci()` / `paired_diff_ci()`：任务级百分位 bootstrap（固定种子，可复现）。
- `wilson()`：比例的 Wilson 区间（样本小时比 bootstrap 稳）。
- `mde_paired()` / `mde_independent()`：测前先算能检测出多大的差距（04 §6.2；arXiv 2609.17394）。
- `compare()`：各配置对基线的成对比较表（成功率 + 区间 + 配对差 + McNemar + Holm）。

结论口径：区间重叠 / Holm 校正后 p ≥ 0.05 → 不宣称更好；每配置 1 次的结论标注为探索性。
"""

from __future__ import annotations

import copy
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

BOOTSTRAP_N = 10_000
SEED = 0
Z = {0.90: 1.6449, 0.95: 1.96, 0.99: 2.5758}
Z_POWER = {0.8: 0.8416, 0.9: 1.2816}


# ---------------------------------------------------------------- 配置生成


@dataclass(frozen=True)
class AblationConfig:
    name: str
    factor: str | None  # None = 基线
    level: str | None
    config: dict[str, Any]  # 完整 RunConfig（dict，可直接写 YAML）
    overrides: dict[str, Any] = field(default_factory=dict)


def deep_merge(base: Mapping[str, Any], over: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(dict(base))
    for k, v in over.items():
        out[k] = (
            deep_merge(out[k], v) if isinstance(v, Mapping) and isinstance(out.get(k), Mapping) else copy.deepcopy(v)
        )
    return out


def ofat(base: Mapping[str, Any], factors: Mapping[str, Mapping[str, Mapping[str, Any]]], *,
         prefix: str | None = None) -> list[AblationConfig]:  # fmt: skip
    """基线 + 每个因素的每个水平各一个配置（其余因素保持基线）。与基线完全相同的水平会被跳过。

    factors = {"context": {"none": {"harness": "configs/harness/no-context-mgmt.yaml"}, ...}, ...}
    """
    stem = prefix or str(base.get("name") or "base")
    out = [AblationConfig(name=f"{stem}", factor=None, level=None, config=deep_merge(base, {"name": stem}))]
    seen = {_key(out[0].config)}
    for factor, levels in factors.items():
        for level, over in levels.items():
            name = f"{stem}--{factor}-{level}"
            cfg = deep_merge(deep_merge(base, over), {"name": name})
            k = _key(cfg)
            if k in seen:
                continue
            seen.add(k)
            out.append(AblationConfig(name=name, factor=factor, level=level, config=cfg, overrides=dict(over)))
    return out


def _key(cfg: Mapping[str, Any]) -> str:
    import json

    return json.dumps({k: v for k, v in cfg.items() if k != "name"}, sort_keys=True, default=str)


def estimate_cost(configs: int, tasks: int, *, attempts: int = 1, per_task_cny: float) -> float:
    return round(configs * tasks * attempts * per_task_cny, 2)


# ---------------------------------------------------------------- 统计


def _binom_two_sided(k: int, n: int) -> float:
    """p = 0.5 的二项分布双侧精确 p 值（McNemar 精确检验）。"""
    if n == 0:
        return 1.0
    k = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


@dataclass(frozen=True)
class McNemar:
    b: int  # A 成功、B 失败
    c: int  # A 失败、B 成功
    n: int  # 配对数
    p_exact: float
    chi2_cc: float  # 连续性校正的卡方统计量（参考）

    @property
    def n_eff(self) -> int:
        return self.b + self.c


def mcnemar(a: Sequence[bool], b: Sequence[bool]) -> McNemar:
    if len(a) != len(b):
        raise ValueError("McNemar 需要等长的配对结果")
    bb = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    cc = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    chi = (abs(bb - cc) - 1) ** 2 / (bb + cc) if bb + cc else 0.0
    return McNemar(b=bb, c=cc, n=len(a), p_exact=round(_binom_two_sided(bb, bb + cc), 6), chi2_cc=round(chi, 4))


def holm(pvals: Sequence[float]) -> list[float]:
    """Holm–Bonferroni 校正后的 p 值（保持输入顺序，单调、截到 1）。"""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = round(running, 6)
    return adj


def _percentile(sorted_stats: list[float], alpha: float) -> tuple[float, float]:
    n = len(sorted_stats)
    return sorted_stats[int(alpha / 2 * n)], sorted_stats[min(n - 1, int((1 - alpha / 2) * n))]


Stat = Callable[[Sequence[float]], float]


def bootstrap_ci(values: Sequence[float | bool], *, stat: Stat | None = None, n: int = BOOTSTRAP_N, seed: int = SEED,
                 alpha: float = 0.05) -> tuple[float, float] | None:  # fmt: skip
    if not values:
        return None
    xs = [float(v) for v in values]
    f = stat or (lambda s: sum(s) / len(s))
    rng = random.Random(seed)
    stats = sorted(f(rng.choices(xs, k=len(xs))) for _ in range(n))
    lo, hi = _percentile(stats, alpha)
    return round(lo, 4), round(hi, 4)


def paired_diff_ci(a: Sequence[bool], b: Sequence[bool], **kw: Any) -> tuple[float, float] | None:
    """成功率差 B − A 的配对 bootstrap 区间（按任务整对重采样）。"""
    if len(a) != len(b):
        raise ValueError("配对结果需要等长")
    return bootstrap_ci([float(y) - float(x) for x, y in zip(a, b, strict=True)], **kw)


def wilson(k: int, n: int, *, conf: float = 0.95) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z = Z[conf]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (round(max(0.0, c - h), 4), round(min(1.0, c + h), 4))


def mde_independent(n: int, *, p: float = 0.5, alpha: float = 0.05, power: float = 0.8) -> float:
    """两组各 n 个独立样本时可检测的最小比例差（正态近似）。"""
    return round((Z[1 - alpha] + Z_POWER[power]) * math.sqrt(2 * p * (1 - p) / n), 4)


def mde_paired(n: int, *, discordant: float = 0.2, alpha: float = 0.05, power: float = 0.8) -> float:
    """配对设计（McNemar）可检测的最小差：discordant = 预期不一致对占比（经验值 0.1–0.3）。"""
    return round((Z[1 - alpha] + Z_POWER[power]) * math.sqrt(discordant / n), 4)


# ---------------------------------------------------------------- 比较表


@dataclass
class Row:
    config: str
    n: int
    solved: int
    rate: float
    wilson: tuple[float, float]
    boot: tuple[float, float] | None
    cost_cny: float | None = None
    diff: float | None = None  # 相对基线
    diff_ci: tuple[float, float] | None = None
    test: McNemar | None = None
    p_holm: float | None = None

    def verdict(self) -> str:
        if self.test is None:
            return "基线"
        if (
            self.p_holm is not None
            and self.p_holm < 0.05
            and self.diff_ci
            and (self.diff_ci[0] > 0 or self.diff_ci[1] < 0)
        ):
            return "更好" if (self.diff or 0) > 0 else "更差"
        return "无显著差异"


def compare(results: Mapping[str, Mapping[str, bool]], baseline: str, *,
            costs: Mapping[str, float] | None = None, seed: int = SEED) -> list[Row]:  # fmt: skip
    """results = {配置: {任务: 是否解决}}；只在与基线共有的任务上配对。"""
    base = results[baseline]
    rows: list[Row] = []
    for name, res in results.items():
        common = sorted(set(res) & set(base)) if name != baseline else sorted(res)
        xs = [res[t] for t in common]
        k = sum(xs)
        row = Row(config=name, n=len(xs), solved=k, rate=round(k / len(xs), 4) if xs else 0.0,
                  wilson=wilson(k, len(xs)), boot=bootstrap_ci(xs, seed=seed),
                  cost_cny=(costs or {}).get(name))  # fmt: skip
        if name != baseline and common:
            a = [base[t] for t in common]
            row.test = mcnemar(a, xs)
            row.diff = round((k - sum(a)) / len(common), 4)
            row.diff_ci = paired_diff_ci(a, xs, seed=seed)
        rows.append(row)
    tested = [r for r in rows if r.test is not None]
    for r, p in zip(tested, holm([r.test.p_exact for r in tested if r.test]), strict=True):
        r.p_holm = p
    return rows


def _pct(x: float) -> str:
    return f"{x:.0%}"


def render_rows(rows: Sequence[Row], *, unit: str = "解决") -> str:
    head = f"| 配置 | {unit} | 比例（Wilson 95%） | 相对基线（配对 bootstrap 95%） | McNemar b/c · n_eff | p（精确） | "
    lines = [head + "p（Holm） | 结论 | ¥ |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        diff = (f"{r.diff:+.0%}（{r.diff_ci[0]:+.0%}～{r.diff_ci[1]:+.0%}）" if r.diff is not None and r.diff_ci
                else "—")  # fmt: skip
        t = r.test
        lines.append(f"| {r.config} | {r.solved}/{r.n} | {_pct(r.rate)}（{_pct(r.wilson[0])}–{_pct(r.wilson[1])}） | "
                     f"{diff} | {f'{t.b}/{t.c} · {t.n_eff}' if t else '—'} | {f'{t.p_exact:.3f}' if t else '—'} | "
                     f"{f'{r.p_holm:.3f}' if r.p_holm is not None else '—'} | {r.verdict()} | "
                     f"{f'{r.cost_cny:.2f}' if r.cost_cny is not None else '—'} |")  # fmt: skip
    return "\n".join(lines)


__all__ = ["AblationConfig", "McNemar", "Row", "bootstrap_ci", "compare", "deep_merge", "estimate_cost", "holm",
           "mcnemar", "mde_independent", "mde_paired", "ofat", "paired_diff_ci", "render_rows", "wilson"]  # fmt: skip
