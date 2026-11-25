# -*- coding: utf-8 -*-
"""把 dataset/ 下两张 CSV 导入 MySQL risk_assessment（幂等，可重复运行）。

表：
  enterprise_info  企业工商信息（59 列，10000 行）
  risk_rating      风险评级信息（19 列，10000 行）

用法：
  .venv\\Scripts\\python.exe scripts\\import_dataset.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd
import pymysql

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(BASE, "dataset")

DB = dict(
    host="127.0.0.1",
    port=3306,
    user="risk_user",
    password="Risk@2026",
    database="risk_assessment",
    charset="utf8mb4",
    autocommit=False,
)

DATE_COLS = [
    "est_date",
    "cancel_date",
    "rev_date",
    "appr_date",
    "open_date",
    "close_date",
]
DEC_COLS = ["reg_cap", "rec_cap"]
RISK_INT = [f"{p}_{i}" for p in ("cai", "s_an", "li_an", "zhi") for i in (1, 2, 3)]


def col_def(name: str) -> str:
    if name in DATE_COLS:
        return "DATE NULL"
    if name in DEC_COLS:
        return "DECIMAL(20,6) NULL"
    if name in RISK_INT or name == "id_num":
        return "INT NULL"
    if name == "zhuce_money":
        return "DECIMAL(20,2) NULL"
    if name == "jing_fan":
        return "TEXT NULL"
    return "VARCHAR(255) NULL"


def create_table(
    cur, table: str, columns: list[str], pk: str, indexes: list[str]
) -> None:
    cur.execute(f"DROP TABLE IF EXISTS `{table}`")
    defs = []
    for c in columns:
        d = col_def(c)
        if c == pk:
            d = d.replace("NULL", "NOT NULL")
        defs.append(f"`{c}` {d}")
    body = (",\n  ").join(defs)
    ddl = f"CREATE TABLE `{table}` (\n  {body},\n  PRIMARY KEY (`{pk}`)"
    for idx in indexes:
        ddl += f",\n  KEY `idx_{idx}` (`{idx}`)"
    ddl += "\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci"
    cur.execute(ddl)


def clean_value(col: str, v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return None
    if col in DATE_COLS:
        ts = pd.to_datetime(s, errors="coerce")
        return None if pd.isna(ts) else ts.date().isoformat()
    if col in DEC_COLS or col == "zhuce_money":
        try:
            return float(s)
        except ValueError:
            return None
    if col in RISK_INT or col == "id_num":
        try:
            return int(float(s))
        except ValueError:
            return None
    return s


def load(table: str, path: str, pk: str, indexes: list[str]) -> int:
    df = pd.read_csv(path, dtype=str, encoding="utf-8")
    cols = list(df.columns)
    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            create_table(cur, table, cols, pk, indexes)
            placeholders = ",".join(["%s"] * len(cols))
            sql = f"INSERT INTO `{table}` ({','.join('`' + c + '`' for c in cols)}) VALUES ({placeholders})"
            rows = []
            for rec in df.itertuples(index=False, name=None):
                rows.append(tuple(clean_value(c, v) for c, v in zip(cols, rec)))
                if len(rows) >= 1000:
                    cur.executemany(sql, rows)
                    rows.clear()
            if rows:
                cur.executemany(sql, rows)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM `{table}`")
            return cur.fetchone()[0]
    finally:
        conn.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    n1 = load(
        "enterprise_info",
        os.path.join(DATASET, "dwd_essential_info_commercial_.csv"),
        "id",
        ["firm_name", "usc_code", "firm_category", "ope_status"],
    )
    print(f"[enterprise_info] 导入 {n1} 行")
    n2 = load(
        "risk_rating",
        os.path.join(DATASET, "ads_company_rating_basis_1w.csv"),
        "id",
        ["name", "qiye_type"],
    )
    print(f"[risk_rating] 导入 {n2} 行")

    conn = pymysql.connect(**DB)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            print("表：", [r[0] for r in cur.fetchall()])
            cur.execute(
                "SELECT COUNT(*) FROM enterprise_info e JOIN risk_rating r ON e.id = r.id"
            )
            print("按 id 可关联行数：", cur.fetchone()[0])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
