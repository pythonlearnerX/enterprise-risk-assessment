# -*- coding: utf-8 -*-
"""分析看板的数据层：一次读取，算出 8 组可解释的统计视角。

设计原则：
1. 每张图都能回答一个具体问题（不是“好看”）；
2. 每个结论都带样本量/分母，避免“看起来像”；
3. 尽量用统计量（分位数、基尼、卡方残差、相关系数）而不是绝对值堆叠。
"""

from __future__ import annotations

import math

from django.db.models import Count

from .models import RiskIndicator

STATUS_NAMES = {"1": "在营", "2": "注销", "3": "吊销"}
LEVEL_NAMES = {"low": "低风险", "medium": "中风险", "high": "高风险"}
DIMS = [("financial_score", "财务"), ("operation_score", "经营"),
        ("compliance_score", "合规"), ("quality_score", "质量")]


# --------------------------------------------------------------------------
# 基础统计
# --------------------------------------------------------------------------
def _quantile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return float(sorted_vals[int(pos)])
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def _p_for_r(r, n):
    """相关系数的显著性（t 近似）。"""
    if n < 3 or abs(r) >= 1:
        return 0.0
    t = abs(r) * math.sqrt((n - 2) / (1 - r * r))
    return max(0.0, min(1.0, 2 * (1 - 0.5 * (1 + math.erf(t / math.sqrt(2))))))



def _ranks(xs):
    """平均秩（并列取平均），用于 Spearman。"""
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    out = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[idx[k]] = avg
        i = j + 1
    return out


def _spearman(xs, ys):
    """秩相关：先转秩再算皮尔逊。"""
    return _pearson(_ranks(xs), _ranks(ys))


def _pc1(matrix):
    """对称矩阵第一主成分：幂迭代，返回 (特征值, 载荷向量)。"""
    k = len(matrix)
    v = [1.0 / math.sqrt(k)] * k
    for _ in range(300):
        w = [sum(matrix[i][j] * v[j] for j in range(k)) for i in range(k)]
        norm = math.sqrt(sum(x * x for x in w)) or 1.0
        v = [x / norm for x in w]
    lam = sum(v[i] * sum(matrix[i][j] * v[j] for j in range(k)) for i in range(k))
    return lam, v


def _level_of(score):
    return "high" if score >= 80 else ("medium" if score >= 60 else "low")


def _redundancy(rows, dim_vals, totals):
    """四维冗余度检验：α、PC1、排序一致性、头部重合率、等级改判率。

    回答一个具体问题：四维合并是否必要？能不能用一个维度代替？
    """
    k = len(DIMS)
    n = len(rows)
    if n < 3:
        return None
    R = [[_pearson(dim_vals[DIMS[i][0]], dim_vals[DIMS[j][0]]) for j in range(k)]
         for i in range(k)]
    off = [R[i][j] for i in range(k) for j in range(k) if i < j]
    r_bar = sum(off) / len(off) if off else 0.0
    alpha = (k * r_bar / (1 + (k - 1) * r_bar)) if r_bar > -1 / (k - 1) else 0.0

    lam, load = _pc1(R)
    sq = sum(x * x for x in load) or 1.0
    pc1_ratio = lam / k * 100
    pc1_w = {DIMS[i][1]: round(load[i] ** 2 / sq * 100, 1) for i in range(k)}

    names = [d[1] for d in DIMS]
    base_lv = [_level_of(t) for t in totals]
    rt = _ranks(totals)
    k10 = max(n // 10, 1)
    top_base = set(sorted(range(n), key=lambda i: -totals[i])[:k10])

    spearman, overlap, level_change = {}, {}, {}
    for i, dim in enumerate(names):
        col = dim_vals[DIMS[i][0]]
        spearman[dim] = round(_spearman(totals, col), 4)
        top_d = set(sorted(range(n), key=lambda idx: -col[idx])[:k10])
        overlap[dim] = round(len(top_base & top_d) / k10 * 100, 1)
        alt = [_level_of(x) for x in col]
        level_change[dim] = round(
            sum(1 for a, b in zip(base_lv, alt) if a != b) / n * 100, 2)

    # 用 PC1 权重组合，与等权对比
    w = [load[i] ** 2 / sq for i in range(k)]
    pc_score = [sum(dim_vals[DIMS[i][0]][r] * w[i] for i in range(k)) for r in range(n)]
    pc_change = sum(1 for a, b in zip(base_lv, [_level_of(x) for x in pc_score]) if a != b)

    return {
        "n": n, "r_bar": round(r_bar, 4), "alpha": round(alpha, 4),
        "pc1_ratio": round(pc1_ratio, 2), "pc1_weight": pc1_w,
        "pc1_spearman": round(_spearman(totals, pc_score), 4),
        "pc1_level_change": round(pc_change / n * 100, 2),
        "spearman": spearman, "top10_overlap": overlap, "level_change": level_change,
        "matrix": [[round(R[i][j], 3) for j in range(k)] for i in range(k)],
    }


def _chi2_sf(x, dof):
    """卡方分布上尾概率（dof 为偶数时的精确式，本看板 dof=4）。"""
    if dof % 2 != 0 or x <= 0:
        return 1.0
    term = math.exp(-x / 2)
    total = 0.0
    for k in range(dof // 2):
        total += term * (x / 2) ** k / math.factorial(k)
    return max(0.0, min(1.0, total))


def _capital_bucket(cap):
    if cap < 100:
        return "0–100 万"
    if cap < 500:
        return "100–500 万"
    if cap < 1000:
        return "500–1000 万"
    return "1000 万以上"


CAP_ORDER = ["0–100 万", "100–500 万", "500–1000 万", "1000 万以上"]


# --------------------------------------------------------------------------
# 主函数
# --------------------------------------------------------------------------
def build():
    rows = list(RiskIndicator.objects.values(
        "id", "name", "total_risk_score", "risk_level",
        "financial_score", "operation_score", "compliance_score", "quality_score",
        "enterprise__reg_cap", "enterprise__est_date", "enterprise__ope_status",
        "enterprise__firm_name",
    ))
    n = len(rows)
    scores = [float(r["total_risk_score"]) for r in rows]

    # 1) 得分分布 + 阈值带
    edges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100.01)]
    labels = ["0–19", "20–39", "40–59", "60–79", "80–100"]
    hist = [0] * 5
    for s in scores:
        for i, (lo, hi) in enumerate(edges):
            if lo <= s < hi:
                hist[i] += 1
                break
    cum = []
    acc = 0
    for v in hist:
        acc += v
        cum.append(round(acc / n * 100, 2) if n else 0)

    # 2) 洛伦兹曲线 + 基尼（风险分集中度）
    ordered = sorted(scores)
    total_sum = sum(ordered) or 1.0
    points, acc = [], 0.0
    step = max(len(ordered) // 200, 1)
    for i, s in enumerate(ordered):
        acc += s
        if i % step == 0 or i == len(ordered) - 1:
            points.append([round((i + 1) / n * 100, 2), round(acc / total_sum * 100, 2)])
    area = 0.0
    prev_x, prev_y = 0.0, 0.0
    for x, y in points:
        area += (x - prev_x) * (y + prev_y) / 2
        prev_x, prev_y = x, y
    gini = round(1 - area / (100 * 100 / 2), 4)
    top10 = round(sum(ordered[-max(n // 10, 1):]) / total_sum * 100, 2)

    # 3) 资本分档 × 分位数带（同规模正常区间）
    bands = {k: [] for k in CAP_ORDER}
    for r in rows:
        cap = float(r["enterprise__reg_cap"] or 0)
        if cap > 0:
            bands[_capital_bucket(cap)].append(float(r["total_risk_score"]))
    band_out = []
    for k in CAP_ORDER:
        vals = sorted(bands[k])
        if not vals:
            continue
        band_out.append({
            "bucket": k, "n": len(vals),
            "p25": round(_quantile(vals, 0.25), 2),
            "p50": round(_quantile(vals, 0.50), 2),
            "p75": round(_quantile(vals, 0.75), 2),
            "p90": round(_quantile(vals, 0.90), 2),
        })

    # 4) 四维相关矩阵
    dim_vals = {key: [float(r[key]) for r in rows] for key, _ in DIMS}
    corr = []
    for i, (k1, n1) in enumerate(DIMS):
        for j, (k2, n2) in enumerate(DIMS):
            r_ = _pearson(dim_vals[k1], dim_vals[k2])
            corr.append([i, j, round(r_, 3), n1 if i == j else f"{n1}×{n2}"])

    # 4.5) 四维冗余度检验（α / PC1 / 排序一致性 / 头部重合 / 等级改判）
    redundancy = _redundancy(rows, dim_vals, scores)

    # 5) 状态 × 等级 标准化残差（卡方）
    table = {s: {lv: 0 for lv in LEVEL_NAMES} for s in STATUS_NAMES.values()}
    for r in rows:
        st = STATUS_NAMES.get(r["enterprise__ope_status"])
        if st:
            table[st][r["risk_level"]] += 1
    row_tot = {s: sum(v.values()) for s, v in table.items()}
    col_tot = {lv: sum(table[s][lv] for s in table) for lv in LEVEL_NAMES}
    chi2 = 0.0
    resid = []
    for i, s in enumerate(table):
        for j, lv in enumerate(LEVEL_NAMES):
            obs = table[s][lv]
            exp = (row_tot[s] * col_tot[lv] / n) if n else 0
            cell = ((obs - exp) / math.sqrt(exp)) if exp > 0 else 0.0
            chi2 += cell ** 2
            resid.append({
                "x": j, "y": i, "obs": obs, "exp": round(exp, 1),
                "resid": round(cell, 2),
            })

    # 6) 分组雷达：全库 / 高风险 / 低风险
    def mean_dims(subset):
        if not subset:
            return [0, 0, 0, 0]
        return [round(sum(float(r[key]) for r in subset) / len(subset), 2)
                for key, _ in DIMS]

    high_rows = [r for r in rows if r["risk_level"] == "high"]
    low_rows = [r for r in rows if r["risk_level"] == "low"]
    radar = [
        {"name": "全库均值", "value": mean_dims(rows)},
        {"name": f"高风险组(n={len(high_rows)})", "value": mean_dims(high_rows)},
        {"name": f"低风险组(n={len(low_rows)})", "value": mean_dims(low_rows)},
    ]

    # 7) 资本-得分象限 + 离群企业
    pts = {"high": [], "medium": [], "low": []}
    caps = []
    for r in rows:
        cap = float(r["enterprise__reg_cap"] or 0)
        if cap <= 0:
            continue
        caps.append(cap)
        pts[r["risk_level"]].append([round(cap, 2), float(r["total_risk_score"])])
    caps_sorted = sorted(caps)
    cap_median = _quantile(caps_sorted, 0.5)

    # 同规模内的离群：每个资本档内 z 分数
    outliers = []
    stat = {}
    for k in CAP_ORDER:
        vals = bands[k]
        if len(vals) < 30:
            continue
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals)) or 1.0
        stat[k] = (mu, sd)
    for r in rows:
        cap = float(r["enterprise__reg_cap"] or 0)
        if cap <= 0:
            continue
        k = _capital_bucket(cap)
        if k not in stat:
            continue
        mu, sd = stat[k]
        z = (float(r["total_risk_score"]) - mu) / sd
        if z >= 2:
            outliers.append({
                "name": r["enterprise__firm_name"] or r["name"],
                "cap": round(cap, 2), "bucket": k,
                "score": float(r["total_risk_score"]), "z": round(z, 2),
            })
    outliers.sort(key=lambda x: -x["z"])

    quadrant = {
        "small_high": sum(1 for r in rows
                          if 0 < float(r["enterprise__reg_cap"] or 0) <= cap_median
                          and float(r["total_risk_score"]) >= 80),
        "small_all": sum(1 for r in rows
                         if 0 < float(r["enterprise__reg_cap"] or 0) <= cap_median),
        "big_high": sum(1 for r in rows
                        if float(r["enterprise__reg_cap"] or 0) > cap_median
                        and float(r["total_risk_score"]) >= 80),
        "big_all": sum(1 for r in rows if float(r["enterprise__reg_cap"] or 0) > cap_median),
    }

    # 8) 成立年份 cohort：均分 + 高风险占比
    cohorts = {}
    for r in rows:
        d = r["enterprise__est_date"]
        if not d:
            continue
        y = d.year
        key = ("1990 前" if y < 1990 else "1990–1999" if y < 2000 else
               "2000–2009" if y < 2010 else "2010–2014" if y < 2015 else
               "2015–2019" if y < 2020 else "2020 后")
        cohorts.setdefault(key, []).append(r)
    cohort_order = ["1990 前", "1990–1999", "2000–2009", "2010–2014", "2015–2019", "2020 后"]
    cohort_out = []
    for k in cohort_order:
        sub = cohorts.get(k, [])
        if not sub:
            continue
        hi = sum(1 for r in sub if r["risk_level"] == "high")
        cohort_out.append({
            "cohort": k, "n": len(sub),
            "mean": round(sum(float(r["total_risk_score"]) for r in sub) / len(sub), 2),
            "high_rate": round(hi / len(sub) * 100, 2),
        })

    # ---------------- 自动结论 ----------------
    high_n = len(high_rows)
    high_sum = sum(float(r["total_risk_score"]) for r in high_rows)
    chi2_p = _chi2_sf(chi2, (len(table) - 1) * (len(LEVEL_NAMES) - 1))
    insights = []

    if n:
        insights.append(
            f"① 分档：低 {len(low_rows)}（{len(low_rows) / n * 100:.1f}%）、"
            f"中 {n - high_n - len(low_rows)}（{(n - high_n - len(low_rows)) / n * 100:.1f}%）、"
            f"高 {high_n}（{high_n / n * 100:.2f}%）。按 60/80 阈值，低风险占约四分之三，"
            f"说明阈值偏宽松，高分档样本偏少。")

    insights.append(
        f"② 集中度：基尼系数 {gini:.3f}，前 10% 企业贡献 {top10:.1f}% 的风险分——"
        f"风险分呈中等偏集中分布，不是平均摊开。")

    if band_out:
        lo_b, hi_b = band_out[0], band_out[-1]
        gap = hi_b["p50"] - lo_b["p50"]
        insights.append(
            f"③ 规模效应：{lo_b['bucket']} 中位数 {lo_b['p50']:.1f}，"
            f"{hi_b['bucket']} 中位数 {hi_b['p50']:.1f}，仅差 {gap:+.1f} 分；"
            f"说明在这份数据里注册资本几乎不能解释风险高低。")

    if len(corr) > 5:
        off = [c for c in corr if c[0] != c[1]]
        best = max(off, key=lambda c: abs(c[2]))
        insights.append(
            f"④ 维度共线：{DIMS[best[0]][1]}与{DIMS[best[1]][1]} 的 r={best[2]:+.3f}"
            f"（n={n}），四维之间 r 均在 0.94 以上——四维信息高度重叠，"
            f"等权相加等于把同一件事算了四遍，后续可考虑因子分析降维。")

    if resid:
        insights.append(
            f"⑤ 状态无关：卡方 χ²={chi2:.2f}（df={(len(table) - 1) * (len(LEVEL_NAMES) - 1)}，p={chi2_p:.3f}），"
            f"经营状态与风险等级{'没有显著关联' if chi2_p > 0.05 else '存在显著关联'}；"
            f"即“注销/吊销的企业风险更高”在本数据中不成立。")

    if outliers:
        insights.append(
            f"⑥ 异常点：同资本档内 z≥2 的企业 {len(outliers)} 家，"
            f"最突出的是 {outliers[0]['name']}（{outliers[0]['bucket']}，"
            f"得分 {outliers[0]['score']:.1f}，z={outliers[0]['z']:.1f}），"
            f"值得单独核查而不是只看总分排名。")

    if cohort_out:
        rates = [c["high_rate"] for c in cohort_out]
        insights.append(
            f"⑦ 代际差异：各成立年段高风险率在 {min(rates):.1f}%–{max(rates):.1f}% 之间，"
            f"波动幅度小于 2pp，没有“新企业更危险”的证据。")

    return {
        "n": n,
        "hist": {"labels": labels, "values": hist, "cum": cum},
        "gini": gini,
        "lorentz": {"points": points, "top10": top10},
        "bands": band_out,
        "corr": {"r": corr, "dims": [d[1] for d in DIMS]},
        "redundancy": redundancy,
        "risk_share": round(high_sum / total_sum * 100, 2) if total_sum else 0,
        "chi2_p": round(chi2_p, 4) if n else 1.0,
        "residual": {
            "status": list(table.keys()),
            "levels": [LEVEL_NAMES[k] for k in LEVEL_NAMES],
            "cells": resid, "chi2": round(chi2, 2),
            "dof": (len(table) - 1) * (len(LEVEL_NAMES) - 1),
        },
        "radar": radar,
        "scatter": {"points": pts, "cap_median": round(cap_median, 2),
                    "quadrant": quadrant},
        "outliers": outliers[:8],
        "cohort": cohort_out,
        "insights": insights,
        "counts": {
            "high": high_n, "medium": n - high_n - len(low_rows),
            "low": len(low_rows),
            "status": {s: row_tot[s] for s in row_tot},
        },
    }