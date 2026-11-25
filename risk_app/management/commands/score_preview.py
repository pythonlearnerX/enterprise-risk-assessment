# -*- coding: utf-8 -*-
"""预览扣分制评分结果（只读，不改库）。"""
from django.core.management.base import BaseCommand

from risk_app.models import RiskIndicator
from risk_app.risk_calc import calc_risk

FIELDS = ["cai_1", "cai_2", "cai_3", "s_an_1", "s_an_2", "s_an_3",
          "li_an_1", "li_an_2", "li_an_3", "zhi_1", "zhi_2", "zhi_3"]


class Command(BaseCommand):
    help = "按扣分制/风险点两种口径预览评分，不写数据库"

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=5, help="打印前 N 家企业")

    def handle(self, *args, **options):
        limit = options["limit"]
        buckets = {"0-59": 0, "60-79": 0, "80-100": 0}
        total_count = 0
        for r in RiskIndicator.objects.all().iterator(chunk_size=2000):
            values = {f: float(getattr(r, f)) for f in FIELDS}
            result = calc_risk(values, mode="count")
            t = result["total"]
            key = "0-59" if t < 60 else ("60-79" if t < 80 else "80-100")
            buckets[key] += 1
            total_count += 1

        self.stdout.write(f"共 {total_count} 条；扣分制（次数口径）分布：")
        for k, v in buckets.items():
            self.stdout.write(f"  {k}: {v} 条 ({v / max(total_count, 1) * 100:.1f}%)")

        self.stdout.write("\n前 %d 家对比（次数口径 vs 风险点口径）：" % limit)
        for r in RiskIndicator.objects.all()[:limit]:
            values = {f: float(getattr(r, f)) for f in FIELDS}
            count_mode = calc_risk(values, mode="count")
            points_mode = calc_risk(values, mode="points")
            self.stdout.write(
                f"  {r.name[:16]:<16} count={count_mode['total']:>6.2f} "
                f"points={points_mode['total']:>6.2f} 库中={float(r.total_risk_score):>6.2f}")