# -*- coding: utf-8 -*-
"""数据批量导入脚本：两张 CSV → MySQL（全量覆盖，各 10000 条）。

用法：.venv\\Scripts\\python.exe data_import.py
"""
import os
import sys
import time
from datetime import datetime

import django
import pandas as pd
import pymysql

pymysql.install_as_MySQLdb()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "risk_project.settings")
django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402

from risk_app.models import Enterprise, RiskIndicator  # noqa: E402

CSV_ENT = os.path.join(BASE_DIR, "dataset", "dwd_essential_info_commercial_.csv")
CSV_RISK = os.path.join(BASE_DIR, "dataset", "ads_company_rating_basis_1w.csv")


def parse_date(s):
    """兼容 2020-01-01 / 2020/1/1 / 2020年1月1日 / 20200101。"""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    s = str(s).strip()
    if not s or s.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_float(v, default=0.0):
    try:
        if v in ("", None) or pd.isna(v):
            return default
        return round(float(v), 2)
    except (TypeError, ValueError):
        return default


def parse_int(v):
    if v in ("", None) or (isinstance(v, float) and pd.isna(v)):
        return None
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    return int(digits) if digits else None


def text(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return None if s.lower() == "nan" or s == "" else s


def ensure_tables():
    existing = set(connection.introspection.table_names())
    if "auth_user" not in existing:
        call_command("migrate", verbosity=0, interactive=False)
        existing = set(connection.introspection.table_names())
    missing = [m for m in (Enterprise, RiskIndicator) if m._meta.db_table not in existing]
    if missing:
        with connection.schema_editor() as editor:
            for model in missing:
                editor.create_model(model)
        print(f"[建表] 自动创建 {', '.join(m._meta.db_table for m in missing)}")
    else:
        print("[建表] 表已存在，跳过")


def clear_data():
    r = RiskIndicator.objects.count()
    e = Enterprise.objects.count()
    if r:
        RiskIndicator.objects.all().delete()
    if e:
        Enterprise.objects.all().delete()
    print(f"[清空] 风险记录 {r} 条、企业记录 {e} 条")


def build_enterprise(row):
    return dict(
        firm_eid=text(row.get("firm_eid")),
        usc_code=text(row.get("usc_code")),
        firm_name=text(row.get("firm_name")) or "未命名企业",
        legal_rep=text(row.get("legal_rep")),
        firm_type=text(row.get("firm_type")),
        firm_category=text(row.get("firm_category")),
        ope_status=text(row.get("ope_status")),
        est_date=parse_date(row.get("est_date")),
        cancel_date=parse_date(row.get("cancel_date")),
        reg_cap=parse_float(row.get("reg_cap")),
        reg_cap_cur=text(row.get("reg_cap_cur")),
        rec_cap=parse_float(row.get("rec_cap")),
        emp_num=parse_int(row.get("emp_num")),
        province=text(row.get("province")),
        city=text(row.get("city")),
        district=text(row.get("district")),
        reg_org=text(row.get("reg_agency")),
        appr_date=parse_date(row.get("appr_date")),
        ope_period=text(row.get("ope_period")),
        reg_address=text(row.get("reg_address")),
        ope_address=text(row.get("ope_address")),
    )


def import_enterprise_data(path):
    df = pd.read_csv(path, dtype=str, low_memory=False)
    objs = [Enterprise(**build_enterprise(r)) for r in df.to_dict("records")]
    Enterprise.objects.bulk_create(objs, batch_size=500, ignore_conflicts=True)
    n = Enterprise.objects.count()
    print(f"[企业] CSV {len(df)} 条 → 库内 {n} 条")
    return n


def build_risk(row, ent):
    v = {f"{p}_{i}": parse_float(row.get(f"{p}_{i}")) for p in ("cai", "s_an", "li_an", "zhi") for i in (1, 2, 3)}
    # 12 项指标各 0–25，合计上限 300；折算成百分制（0–100）后入库
    total = min(100.0, round(sum(v.values()) / 3, 2))  # 兜底：任何异常数据都不超过 100
    level = "low" if total < 60 else ("medium" if total < 80 else "high")
    return RiskIndicator(
        enterprise=ent,
        name=text(row.get("name")) or ent.firm_name,
        cai_1=v["cai_1"], cai_2=v["cai_2"], cai_3=v["cai_3"],
        s_an_1=v["s_an_1"], s_an_2=v["s_an_2"], s_an_3=v["s_an_3"],
        li_an_1=v["li_an_1"], li_an_2=v["li_an_2"], li_an_3=v["li_an_3"],
        zhi_1=v["zhi_1"], zhi_2=v["zhi_2"], zhi_3=v["zhi_3"],
        financial_score=round((v["cai_1"] + v["cai_2"] + v["cai_3"]) * 4 / 3, 2),
        operation_score=round((v["s_an_1"] + v["s_an_2"] + v["s_an_3"]) * 4 / 3, 2),
        compliance_score=round((v["li_an_1"] + v["li_an_2"] + v["li_an_3"]) * 4 / 3, 2),
        quality_score=round((v["zhi_1"] + v["zhi_2"] + v["zhi_3"]) * 4 / 3, 2),
        total_risk_score=total,
        risk_level=level,
    )


def import_risk_data(path):
    df = pd.read_csv(path, dtype=str, low_memory=False)
    name_to_ent = {e.firm_name: e for e in Enterprise.objects.all()}
    missing = sorted({text(r["name"]) for r in df.to_dict("records")
                      if text(r["name"]) and text(r["name"]) not in name_to_ent})
    if missing:
        Enterprise.objects.bulk_create(
            [Enterprise(firm_name=n, firm_category="E") for n in missing],
            batch_size=500, ignore_conflicts=True)
        name_to_ent = {e.firm_name: e for e in Enterprise.objects.all()}
        print(f"[补建] 风险表独有企业 {len(missing)} 家")

    objs = [build_risk(r, name_to_ent[text(r["name"])]) for r in df.to_dict("records")
            if text(r["name"]) in name_to_ent]
    RiskIndicator.objects.bulk_create(objs, batch_size=500)
    n = RiskIndicator.objects.count()
    print(f"[风险] CSV {len(df)} 条 → 入库 {len(objs)} 条，库内 {n} 条")
    return n


def main():
    t0 = time.time()
    ensure_tables()
    clear_data()
    import_enterprise_data(CSV_ENT)
    import_risk_data(CSV_RISK)
    print(f"[完成] 企业 {Enterprise.objects.count()} 条、风险 {RiskIndicator.objects.count()} 条，"
          f"耗时 {time.time() - t0:.1f} 秒")


if __name__ == "__main__":
    main()