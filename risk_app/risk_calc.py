# -*- coding: utf-8 -*-
"""风险评分函数（扣分制）。

设计依据（课程 PPT）：
- 四个维度，每个维度满分 25 分，合计 100 分；
- 每个维度含 3 项指标（近 1/2/3 年），取三项平均次数；
- 每发生 1 次扣 1 分，单维度不出现负分；
- 综合得分 = 四个维度得分之和，范围 [0, 100]。

关键口径（容易讲错的地方）
--------------------------
“扣分制”扣的是**安全分**：每维初始 25 分是安全上限，发生事件就往下扣。
但本系统对外展示、判断等级用的是**风险分**：

    安全分 = max(0, 25 − 平均次数 × 每次扣分)
    风险分 = 25 − 安全分 = min(平均次数 × 每次扣分, 25)

所以**风险分越大越危险**，与阈值“<60 低 / 60–80 中 / ≥80 高”一致。
（早期版本这里直接返回了“安全分”却当成风险分用，导致 3 次事件算出 88 分被判高风险，
  语义是反的；2026-11-19 已修正，见 tests.RiskCalcTests。）

两种计分模式
------------
mode="count"
    输入是“次数”，如 cai_1=3 表示近 1 年被裁判 3 次。
    按上面的扣分规则先算安全分，再转成风险分（即被扣掉的分）。

mode="points"
    输入是 0–25 的“风险点”（当前数据集就是这种口径，数值越大越危险）。
    维度风险分 = 加权平均风险点；总分 = 四维之和（0–100）。

两种模式都保证总分落在 [0, 100]，四维之和 = 总分，且**都是越大越危险**。
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Sequence

MAX_PER_DIMENSION = 25.0
MAX_TOTAL = 100.0
DEDUCTION_PER_EVENT = 1.0
LEVELS = ((60.0, "low", "低风险"), (80.0, "medium", "中风险"), (100.01, "high", "高风险"))

# 指标定义：键名、中文名、所属维度
INDICATORS: Dict[str, Dict[str, str]] = {
    "cai_1": {"label": "财务-近1年被裁判次数", "dim": "financial"},
    "cai_2": {"label": "财务-近2年被裁判次数", "dim": "financial"},
    "cai_3": {"label": "财务-近3年被裁判次数", "dim": "financial"},
    "s_an_1": {"label": "经营-近1年立案数", "dim": "operation"},
    "s_an_2": {"label": "经营-近2年立案数", "dim": "operation"},
    "s_an_3": {"label": "经营-近3年立案数", "dim": "operation"},
    "li_an_1": {"label": "合规-近1年被立案次数", "dim": "compliance"},
    "li_an_2": {"label": "合规-近2年被立案次数", "dim": "compliance"},
    "li_an_3": {"label": "合规-近3年被立案次数", "dim": "compliance"},
    "zhi_1": {"label": "质量-近1年被执行次数", "dim": "quality"},
    "zhi_2": {"label": "质量-近2年被执行次数", "dim": "quality"},
    "zhi_3": {"label": "质量-近3年被执行次数", "dim": "quality"},
}

DIMENSIONS: Dict[str, Dict[str, object]] = {
    "financial": {"label": "财务风险", "indicators": ["cai_1", "cai_2", "cai_3"]},
    "operation": {"label": "经营风险", "indicators": ["s_an_1", "s_an_2", "s_an_3"]},
    "compliance": {"label": "合规风险", "indicators": ["li_an_1", "li_an_2", "li_an_3"]},
    "quality": {"label": "质量风险", "indicators": ["zhi_1", "zhi_2", "zhi_3"]},
}

# 默认权重：三项等权；维度等权（每维 25 分）
DEFAULT_YEAR_WEIGHTS = (1 / 3, 1 / 3, 1 / 3)
DEFAULT_DIM_WEIGHTS = {"financial": 0.25, "operation": 0.25,
                       "compliance": 0.25, "quality": 0.25}


def _clamp(value: float, low: float = 0.0, high: float = 25.0) -> float:
    return max(low, min(high, float(value)))


def _weighted_mean(values: Sequence[float], weights: Sequence[float]) -> float:
    total = sum(weights)
    if not values or total <= 0:
        return 0.0
    return sum(float(v) * w for v, w in zip(values, weights)) / total


def risk_level(total: float) -> tuple[str, str]:
    """返回 (level 代码, 中文)。阈值：<60 低，60–80 中，≥80 高。"""
    for upper, code, label in LEVELS:
        if total < upper:
            return code, label
    return "high", "高风险"


def calc_risk(values: Mapping[str, float], mode: str = "count",
              year_weights: Sequence[float] | None = None,
              dim_weights: Mapping[str, float] | None = None) -> dict:
    """计算风险得分。

    参数
    ----
    values: 12 项指标，键为 cai_1…zhi_3。
    mode: "count"（次数，越大越危险、扣分）或 "points"（0–25 风险点）。
    year_weights: 近 1/2/3 年权重，默认等权 (1/3, 1/3, 1/3)。
    dim_weights: 四维权重，默认各 0.25（等价每维 25 分）。

    返回
    ----
    dict: dimensions（每维得分/均值）、total、level、level_label、mode、formula。
    """
    if mode not in ("count", "points"):
        raise ValueError("mode 只能是 count 或 points")
    year_weights = tuple(year_weights or DEFAULT_YEAR_WEIGHTS)
    dim_weights = dict(dim_weights or DEFAULT_DIM_WEIGHTS)

    dims: Dict[str, dict] = {}
    total = 0.0
    for key, meta in DIMENSIONS.items():
        keys = meta["indicators"]
        missing = [k for k in keys if k not in values]
        if missing:
            raise KeyError(f"缺少指标：{missing}")
        raw = [float(values[k]) for k in keys]
        avg = _weighted_mean(raw, year_weights)
        if mode == "count":
            # 扣分制：满分 25 是“安全分”，每 1 次扣 1 分；扣掉的分才是风险分
            deduct = _clamp(avg * DEDUCTION_PER_EVENT)          # 被扣掉的分
            score = deduct                                       # 风险分 = 扣分
            safe = MAX_PER_DIMENSION - deduct                    # 剩余安全分
        else:
            # 风险点口径：0–25，越大越危险，直接作为维度风险分
            score = _clamp(avg)
            deduct = score
            safe = MAX_PER_DIMENSION - score
        weight = float(dim_weights.get(key, 0.25))
        contribution = score * weight * (MAX_TOTAL / MAX_PER_DIMENSION)
        total += contribution
        dims[key] = {
            "label": meta["label"],
            "raw": raw,
            "average": round(avg, 4),
            "score": round(score, 2),      # 风险分（越大越危险）
            "deduct": round(deduct, 2),    # 扣掉的分（count 口径）
            "safe": round(safe, 2),        # 剩余安全分 = 25 − 风险分
            "weight": weight,
            "contribution": round(contribution, 2),
        }

    total = _clamp(total, 0.0, MAX_TOTAL)
    code, label = risk_level(total)
    return {
        "dimensions": dims,
        "total": round(total, 2),
        "level": code,
        "level_label": label,
        "mode": mode,
        "formula": ("安全分 = max(0, 25 − 平均次数×1)；风险分 = 25 − 安全分；"
                    "总分 = Σ 风险分×权重×4"
                    if mode == "count"
                    else "维度风险分 = 平均风险点(0–25)；总分 = Σ 风险分×权重×4"),
    }


def describe(values: Mapping[str, float], **kwargs) -> str:
    """把计算过程转成一段可读文本，便于写报告/日志。"""
    result = calc_risk(values, **kwargs)
    lines = [f"计分模式：{result['mode']}（{result['formula']}）"]
    for key, d in result["dimensions"].items():
        if result["mode"] == "count":
            lines.append(
                f"{d['label']}：原始 {d['raw']}，平均次数 {d['average']:.2f}，"
                f"安全分 {d['safe']:.2f}，扣分 {d['deduct']:.2f}（即风险分），"
                f"贡献 {d['contribution']:.2f}"
            )
        else:
            lines.append(
                f"{d['label']}：原始 {d['raw']}，平均风险点 {d['average']:.2f}，"
                f"风险分 {d['score']:.2f}，贡献 {d['contribution']:.2f}"
            )
    lines.append(f"综合得分：{result['total']:.2f}（{result['level_label']}）")
    return "\n".join(lines)