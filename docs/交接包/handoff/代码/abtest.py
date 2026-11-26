# -*- coding: utf-8 -*-
"""A/B 测试核心工具：分桶、两比例检验、置信区间、样本量、决策建议。

全部用标准库实现，不依赖 scipy/numpy，方便在课程环境直接运行。
"""

from __future__ import annotations

import hashlib
import math

Z_95 = 1.959963984540054
Z_80 = 0.8416212335729143


# --------------------------------------------------------------------------
# 1. 分桶
# --------------------------------------------------------------------------
def bucket(user_key: str, exp_key: str, ratio: float = 0.5) -> str:
    """按 md5(user_key + exp_key) 稳定分桶，返回 "A" 或 "B"。

    同一个用户在同一实验里永远落到同一组（避免刷新换组，污染效果）；
    不同实验之间互相独立（加 exp_key 参与哈希）。
    """
    raw = f"{exp_key}:{user_key}".encode("utf-8")
    value = int(hashlib.md5(raw).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "B" if value < ratio else "A"


# --------------------------------------------------------------------------
# 2. 分布函数
# --------------------------------------------------------------------------
def _phi(x: float) -> float:
    """标准正态分布函数。"""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def p_value_two_sided(z: float) -> float:
    return max(0.0, min(1.0, 2.0 * (1.0 - _phi(abs(z)))))


# --------------------------------------------------------------------------
# 3. 两比例检验
# --------------------------------------------------------------------------
def proportion_test(a_conv: int, a_n: int, b_conv: int, b_n: int) -> dict:
    """两独立比例 z 检验（pooled），返回转化率、提升、p 值、95% 置信区间。"""
    a_conv, b_conv = max(0, a_conv), max(0, b_conv)
    a_n, b_n = max(0, a_n), max(0, b_n)
    if a_n == 0 or b_n == 0:
        return {
            "a_rate": 0.0, "b_rate": 0.0, "diff": 0.0, "lift": 0.0,
            "z": 0.0, "p_value": 1.0, "ci_low": 0.0, "ci_high": 0.0,
            "significant": False, "enough": False,
        }

    a_rate = a_conv / a_n
    b_rate = b_conv / b_n
    diff = b_rate - a_rate
    lift = (diff / a_rate) if a_rate > 0 else 0.0

    pooled = (a_conv + b_conv) / (a_n + b_n)
    se_pooled = math.sqrt(pooled * (1 - pooled) * (1 / a_n + 1 / b_n)) if 0 < pooled < 1 else 0.0
    z = diff / se_pooled if se_pooled > 0 else 0.0
    p = p_value_two_sided(z)

    se_diff = math.sqrt(
        a_rate * (1 - a_rate) / a_n + b_rate * (1 - b_rate) / b_n
    )
    ci_low, ci_high = diff - Z_95 * se_diff, diff + Z_95 * se_diff

    return {
        "a_rate": round(a_rate, 4),
        "b_rate": round(b_rate, 4),
        "diff": round(diff, 4),
        "lift": round(lift, 4),
        "z": round(z, 4),
        "p_value": round(p, 5),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "significant": p < 0.05,
        "enough": (a_n >= 100 and b_n >= 100),
    }


# --------------------------------------------------------------------------
# 4. 样本量 / 决策
# --------------------------------------------------------------------------
def required_sample_size(p1: float, p2: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """计算每组所需样本量（双侧）。p1 基线，p2 期望值。"""
    if p1 <= 0 or p2 <= 0 or abs(p2 - p1) < 1e-9:
        return 0
    z_alpha = Z_95 if abs(alpha - 0.05) < 1e-6 else 1.959963984540054
    z_beta = Z_80 if abs(power - 0.8) < 1e-6 else 0.8416212335729143
    p_bar = (p1 + p2) / 2
    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
        + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    return int(math.ceil(numerator / ((p2 - p1) ** 2)))


def decide(a_conv: int, a_n: int, b_conv: int, b_n: int,
           min_sample: int = 100) -> dict:
    """给出决策建议：上线 B / 保留 A / 继续采集 / 样本不足。"""
    stats = proportion_test(a_conv, a_n, b_conv, b_n)
    n_min = max(min_sample, 0)

    if a_n < n_min or b_n < n_min:
        verdict, reason = "continue", f"两组样本均需 ≥{n_min}，当前 {a_n}/{b_n}"
    elif not stats["significant"]:
        verdict = "continue"
        reason = f"p={stats['p_value']:.3f} ≥ 0.05，差异不显著"
    elif stats["diff"] > 0:
        verdict, reason = "ship_b", f"B 高 {stats['lift'] * 100:.1f}%（p={stats['p_value']:.3f}）"
    else:
        verdict, reason = "keep_a", f"B 低 {abs(stats['lift']) * 100:.1f}%（p={stats['p_value']:.3f}）"

    label = {
        "ship_b": "上线 B",
        "keep_a": "保留 A",
        "continue": "继续采集",
    }[verdict]
    return {**stats, "verdict": verdict, "verdict_label": label, "reason": reason}


def format_report(stats: dict) -> str:
    """把统计结果转成一段可读文本。"""
    return (
        f"A {stats['a_rate'] * 100:.2f}% vs B {stats['b_rate'] * 100:.2f}%，"
        f"差值 {stats['diff'] * 100:+.2f}pp（相对 {stats['lift'] * 100:+.1f}%），"
        f"z={stats['z']:.3f}，p={stats['p_value']:.4f}，"
        f"95%CI [{stats['ci_low'] * 100:+.2f}, {stats['ci_high'] * 100:+.2f}]pp"
    )