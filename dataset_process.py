# -*- coding: utf-8 -*-
"""数据集梳理脚本：读取企业工商数据与风险评级数据，完成预览、质量检查与分布统计。

对应《实训指导书_01》任务 4：
  企业数据：加载 → 预览 → 企业类别分布 → 经营状态分布
  风险数据：加载 → 预览 → 四类风险指标概览 → 12 项指标概况
运行：
  .venv\\Scripts\\python.exe dataset_process.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

# Windows 控制台默认 GBK，直接打印中文可能报 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "dataset")

# 实际文件名以 dataset/ 目录为准（老师下发的企业表名被截断为 commercial_）
ENTERPRISE_FULL = os.path.join(DATASET_DIR, "dwd_essential_info_commercial_.csv")
ENTERPRISE_SAMPLE = os.path.join(
    DATASET_DIR, "dwd_essential_info_commercial_sample.csv"
)
RISK_FULL = os.path.join(DATASET_DIR, "ads_company_rating_basis_1w.csv")
RISK_SAMPLE = os.path.join(DATASET_DIR, "ads_company_rating_basis_sample.csv")

# 提交截图用全量（10000 条）；调 True 用 10 条样本快速验证
USE_SAMPLE = False

# 字段英文名 → 中文名（企业表，选关键字段展示）
ENTERPRISE_CN = {
    "id": "企业唯一标识",
    "firm_eid": "企业EID",
    "firm_name": "企业名称",
    "usc_code": "统一社会信用代码",
    "firm_category": "企业类别(E企业/P个体户)",
    "ope_status": "经营状态(1在营/2注销)",
    "legal_rep": "法定代表人",
    "est_date": "成立日期",
    "reg_cap": "注册资本(万元)",
    "ind_econ_name": "行业名称",
    "province": "省份",
    "city": "城市",
    "district": "区县",
    "ope_address": "经营地址",
    "emp_num": "员工人数",
    "ope_scope": "经营范围",
}

# 字段英文名 → 中文名（风险表）
RISK_CN = {
    "id": "企业唯一标识",
    "name": "企业名称",
    "cai_1": "近1年裁判次数",
    "cai_2": "近2年裁判次数",
    "cai_3": "近3年裁判次数",
    "s_an_1": "近1年立案数",
    "s_an_2": "近2年立案数",
    "s_an_3": "近3年立案数",
    "li_an_1": "近1年被立案次数",
    "li_an_2": "近2年被立案次数",
    "li_an_3": "近3年被立案次数",
    "zhi_1": "近1年被执行次数",
    "zhi_2": "近2年被执行次数",
    "zhi_3": "近3年被执行次数",
    "f_ren": "法定代表人",
    "zhuce_money": "注册资本(万元)",
    "jing_fan": "经营范围",
    "qiye_type": "企业类型",
    "id_num": "编号",
}

RISK_INDICATORS = [
    f"{p}_{i}" for p in ("cai", "s_an", "li_an", "zhi") for i in (1, 2, 3)
]

# 质量检查关注的关键字段
ENTERPRISE_KEY_COLS = [
    "firm_name",
    "usc_code",
    "legal_rep",
    "est_date",
    "reg_cap",
    "province",
    "city",
    "ind_econ_name",
]
RISK_KEY_COLS = ["name", "f_ren", "zhuce_money", "qiye_type"]


def _read_csv(path: str) -> pd.DataFrame:
    """统一 dtype=str 读取，避免编号类字段被自动转成数字。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"数据文件不存在: {path}")
    # pandas 3 中 dtype=str 对应字符串 dtype，这里保持显式声明
    return pd.read_csv(path, dtype=str, encoding="utf-8")


def _missing_report(df: pd.DataFrame, cols: list[str]) -> None:
    """输出关键字段的缺失情况：NaN 与空字符串分开统计。"""
    print("  关键字段缺失情况（NaN / 空字符串 / 缺失率）：")
    total = len(df)
    for col in cols:
        if col not in df.columns:
            print(f"    - {col:<18} 字段不存在")
            continue
        s = df[col]
        nan_cnt = int(s.isna().sum())
        blank_cnt = int((s.fillna("").str.strip() == "").sum() - nan_cnt)
        missing = nan_cnt + blank_cnt
        print(f"    - {col:<18} {nan_cnt:>6} / {blank_cnt:>6} / {missing / total:.2%}")


def load_enterprise_data(use_sample: bool = USE_SAMPLE) -> pd.DataFrame:
    """读取企业工商 CSV（全量或样本），统一 dtype=str。"""
    path = ENTERPRISE_SAMPLE if use_sample else ENTERPRISE_FULL
    df = _read_csv(path)
    print(f"[企业数据] 加载完成：{len(df)} 条记录，{len(df.columns)} 个字段")
    return df


def preview_enterprise(df: pd.DataFrame, n: int = 5) -> None:
    """打印前 n 条（中文列名）、数据形状与关键字段缺失。"""
    cols = [
        c
        for c in [
            "firm_name",
            "usc_code",
            "firm_category",
            "ope_status",
            "legal_rep",
            "est_date",
            "reg_cap",
        ]
        if c in df.columns
    ]
    print(f"\n[企业数据] 形状：{df.shape[0]} 行 × {df.shape[1]} 列")
    print(f"  字段：{', '.join(df.columns[:8])} ...（共 {df.shape[1]} 个）")
    print(f"\n  前 {n} 条（关键字段，中文列名）：")
    print(
        df[cols]
        .head(n)
        .rename(columns=ENTERPRISE_CN)
        .to_string(index=False, max_colwidth=14)
    )
    _missing_report(df, ENTERPRISE_KEY_COLS)
    dup = int(df["id"].duplicated().sum()) if "id" in df.columns else -1
    print(f"  主键 id 重复行数：{dup}")


def show_enterprise_category(df: pd.DataFrame) -> None:
    """统计 1：企业类别分布（E=企业，P=个体户）。"""
    label = {"E": "E 企业", "P": "P 个体户"}
    vc = df["firm_category"].value_counts(dropna=False)
    total = len(df)
    print("\n[企业数据] 统计 1：企业类别分布")
    for k, v in vc.items():
        key = "缺失" if pd.isna(k) else str(k)
        print(f"  {label.get(key, key):<12} {v:>6} 条  {v / total:.2%}")


def show_enterprise_status(df: pd.DataFrame) -> None:
    """统计 2：经营状态分布（1=在营，2=注销，3=吊销）。"""
    label = {"1": "1 在营", "2": "2 注销", "3": "3 吊销"}
    vc = df["ope_status"].value_counts(dropna=False)
    total = len(df)
    print("\n[企业数据] 统计 2：经营状态分布")
    for k, v in vc.items():
        key = "缺失" if pd.isna(k) else str(k)
        print(f"  {label.get(key, key + ' 其他'):<12} {v:>6} 条  {v / total:.2%}")


def load_risk_data(use_sample: bool = USE_SAMPLE) -> pd.DataFrame:
    """读取风险评级 CSV（全量或样本），统一 dtype=str。"""
    path = RISK_SAMPLE if use_sample else RISK_FULL
    df = _read_csv(path)
    print(f"\n[风险数据] 加载完成：{len(df)} 条记录，{len(df.columns)} 个字段")
    return df


def preview_risk(df: pd.DataFrame, n: int = 5) -> None:
    """打印前 n 条（中文列名）、数据形状与关键字段缺失。"""
    cols = [
        c
        for c in [
            "name",
            "cai_1",
            "s_an_1",
            "li_an_1",
            "zhi_1",
            "zhuce_money",
            "qiye_type",
        ]
        if c in df.columns
    ]
    print(f"\n[风险数据] 形状：{df.shape[0]} 行 × {df.shape[1]} 列")
    print(f"\n  前 {n} 条（关键字段，中文列名）：")
    print(
        df[cols].head(n).rename(columns=RISK_CN).to_string(index=False, max_colwidth=14)
    )
    _missing_report(df, RISK_KEY_COLS)
    dup = int(df["id"].duplicated().sum()) if "id" in df.columns else -1
    print(f"  主键 id 重复行数：{dup}")


def show_risk_indicators(df: pd.DataFrame) -> None:
    """统计 1：四类风险指标（裁判 / 立案 / 被立案 / 被执行）概览。"""
    total = len(df)
    groups = {
        "裁判文书": ["cai_1", "cai_2", "cai_3"],
        "立案": ["s_an_1", "s_an_2", "s_an_3"],
        "被立案": ["li_an_1", "li_an_2", "li_an_3"],
        "被执行": ["zhi_1", "zhi_2", "zhi_3"],
    }
    print("\n[风险数据] 统计 1：四类风险指标概览（按近 1 年字段看）")
    print(
        f"  {'类别':<8}{'指标':<8}{'均值':>8}{'最大':>8}{'非零企业':>10}{'非零占比':>10}"
    )
    for name, cols in groups.items():
        col = cols[0]
        s = pd.to_numeric(df[col], errors="coerce")
        nonzero = int((s.fillna(0) > 0).sum())
        print(
            f"  {name:<8}{col:<8}{s.mean():>8.2f}{s.max():>8.0f}{nonzero:>10}{nonzero / total:>10.2%}"
        )


def show_risk_summary(df: pd.DataFrame) -> None:
    """统计 2：12 项指标总体概况（均值、最大值、非零占比、全零企业）。"""
    total = len(df)
    data = df[RISK_INDICATORS].apply(pd.to_numeric, errors="coerce").fillna(0)
    print("\n[风险数据] 统计 2：12 项指标总体概况")
    print(
        f"  {'指标':<10}{'中文名':<16}{'均值':>8}{'最大':>8}{'非零企业':>10}{'非零占比':>10}"
    )
    for col in RISK_INDICATORS:
        s = data[col]
        nonzero = int((s > 0).sum())
        print(
            f"  {col:<10}{RISK_CN[col]:<16}{s.mean():>8.2f}{s.max():>8.0f}{nonzero:>10}{nonzero / total:>10.2%}"
        )

    all_zero = int((data.sum(axis=1) == 0).sum())
    print(f"\n  12 项全为 0 的企业：{all_zero} 条（{all_zero / total:.2%}）")
    if all_zero / total >= 0.5:
        print("  → 多数企业无司法记录，风险评分应按“扣分制”设计")
    else:
        print(
            "  → 本数据中多数企业已有非零风险记录，与指导书“多数为 0”的假设不同，评分方案需按实际分布调整"
        )


def main() -> None:
    print("=" * 72)
    print(f"数据集梳理　模式：{'样本' if USE_SAMPLE else '全量'}　目录：{DATASET_DIR}")
    print("=" * 72)

    ent_df = load_enterprise_data()
    preview_enterprise(ent_df)
    show_enterprise_category(ent_df)
    show_enterprise_status(ent_df)

    risk_df = load_risk_data()
    preview_risk(risk_df)
    show_risk_indicators(risk_df)
    show_risk_summary(risk_df)

    print("\n" + "=" * 72)
    print("完成：企业数据 {} 条、风险数据 {} 条".format(len(ent_df), len(risk_df)))
    print("=" * 72)


if __name__ == "__main__":
    main()
