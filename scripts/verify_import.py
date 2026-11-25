# -*- coding: utf-8 -*-
"""生成数据核对记录（记录数、非空率、分布）。"""
import os
import sys

import django

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "risk_project.settings")
django.setup()

from django.db.models import Count  # noqa: E402

from risk_app.models import Enterprise, RiskIndicator  # noqa: E402


def rate(model, field):
    total = model.objects.count()
    notnull = model.objects.exclude(**{f"{field}__isnull": True}).count()
    return f"{notnull / total:.1%}" if total else "-"


def main():
    e_total = Enterprise.objects.count()
    r_total = RiskIndicator.objects.count()
    print(f"企业记录数：{e_total}")
    print(f"风险记录数：{r_total}")
    print("关键字段非空率：")
    for f in ("usc_code", "legal_rep", "reg_cap", "est_date", "emp_num", "city"):
        print(f"  enterprise.{f}: {rate(Enterprise, f)}")
    for f in ("total_risk_score", "risk_level"):
        print(f"  risk_indicator.{f}: {rate(RiskIndicator, f)}")

    print("经营状态分布：")
    for row in Enterprise.objects.values("ope_status").annotate(n=Count("id")).order_by("-n"):
        print(f"  {row['ope_status'] or '空'}: {row['n']}")
    print("风险等级分布：")
    for row in RiskIndicator.objects.values("risk_level").annotate(n=Count("id")).order_by("-n"):
        print(f"  {row['risk_level']}: {row['n']}")
    print("企业类别分布：")
    for row in Enterprise.objects.values("firm_category").annotate(n=Count("id")).order_by("-n"):
        print(f"  {row['firm_category'] or '空'}: {row['n']}")


if __name__ == "__main__":
    main()