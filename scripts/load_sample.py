# -*- coding: utf-8 -*-
"""导入样本数据（前 200 条），用于工程联调与答辩演示。"""
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "risk_project.settings")

import django  # noqa: E402

django.setup()

from risk_app.models import Enterprise, RiskIndicator  # noqa: E402


def to_date(v):
    ts = pd.to_datetime(v, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def to_dec(v, default=0):
    try:
        f = float(v)
        if pd.isna(f):
            return default
        return round(f, 2)
    except (TypeError, ValueError):
        return default


def to_int(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    digits = "".join(ch for ch in str(v) if ch.isdigit())
    return int(digits) if digits else None


e = pd.read_csv(os.path.join(BASE, "dataset", "dwd_essential_info_commercial_.csv"),
                dtype=str, nrows=200)
r = pd.read_csv(os.path.join(BASE, "dataset", "ads_company_rating_basis_1w.csv"), dtype=str)

Enterprise.objects.all().delete()

objs = []
for row in e.itertuples(index=False):
    d = row._asdict()
    objs.append(Enterprise(
        firm_eid=d.get("firm_eid"), usc_code=d.get("usc_code"),
        firm_name=d.get("firm_name") or "未命名",
        legal_rep=d.get("legal_rep"), firm_type=d.get("firm_type"),
        firm_category=d.get("firm_category"), ope_status=d.get("ope_status"),
        est_date=to_date(d.get("est_date")), cancel_date=to_date(d.get("cancel_date")),
        reg_cap=to_dec(d.get("reg_cap")), reg_cap_cur=d.get("reg_cap_cur"),
        rec_cap=to_dec(d.get("rec_cap")), emp_num=to_int(d.get("emp_num")),
        province=d.get("province"), city=d.get("city"), district=d.get("district"),
        reg_org=d.get("reg_agency"), appr_date=to_date(d.get("appr_date")),
        ope_period=d.get("ope_period"), reg_address=d.get("reg_address"),
        ope_address=d.get("ope_address"),
    ))
Enterprise.objects.bulk_create(objs, batch_size=200, ignore_conflicts=True)

name2id = dict(Enterprise.objects.values_list("firm_name", "id"))
r = r[r["name"].isin(name2id)]
RiskIndicator.objects.all().delete()
risks = []
for row in r.itertuples(index=False):
    d = row._asdict()
    vals = [to_dec(d.get(f"{p}_{i}")) for p in ("cai", "s_an", "li_an", "zhi") for i in (1, 2, 3)]
    total = sum(vals)
    level = "low" if total < 60 else ("medium" if total < 80 else "high")
    risks.append(RiskIndicator(
        enterprise_id=name2id[d["name"]], name=d.get("name") or "",
        cai_1=vals[0], cai_2=vals[1], cai_3=vals[2],
        s_an_1=vals[3], s_an_2=vals[4], s_an_3=vals[5],
        li_an_1=vals[6], li_an_2=vals[7], li_an_3=vals[8],
        zhi_1=vals[9], zhi_2=vals[10], zhi_3=vals[11],
        total_risk_score=total, risk_level=level,
        risk_description="样本数据，评分仅用于联调演示",
    ))
RiskIndicator.objects.bulk_create(risks, batch_size=200)

print("enterprise:", Enterprise.objects.count(), "risk:", RiskIndicator.objects.count())