# -*- coding: utf-8 -*-
"""生成演示用的企业年度评分快照。

注意：原始数据集只有一次快照，没有真实历史。这里生成的 2023–2025 分数是
按当前得分做确定性缩放得到的**模拟值**，全部带 note 标记，页面会显示“模拟”徽标。
请勿用于任何真实统计或结论。
"""
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand
from django.db import transaction

from risk_app.models import Enterprise, RiskIndicator, RiskSnapshot

YEARS = [(2023, Decimal("0.90")), (2024, Decimal("0.95")), (2025, Decimal("1.00"))]
TOP_N = 8


class Command(BaseCommand):
    help = "为得分最高的若干企业生成演示用年度快照（模拟数据）"

    def add_arguments(self, parser):
        parser.add_argument("--top", type=int, default=TOP_N,
                            help="取当前得分最高的前 N 家企业，默认 8")

    @transaction.atomic
    def handle(self, *args, **options):
        top = options["top"]
        rows = list(RiskIndicator.objects.select_related("enterprise")
                    .order_by("-total_risk_score")[:top])
        created, skipped = 0, 0
        for r in rows:
            ent = r.enterprise
            base = Decimal(str(r.total_risk_score))
            for year, factor in YEARS:
                score = min(Decimal("100"), (base * factor).quantize(Decimal("0.01"),
                                                                    rounding=ROUND_HALF_UP))
                level = "low" if score < 60 else ("medium" if score < 80 else "high")
                if RiskSnapshot.objects.filter(enterprise=ent, year=year).exists():
                    skipped += 1
                    continue
                RiskSnapshot.objects.create(enterprise=ent, year=year, total_score=score,
                                            level=level, note="演示模拟（非真实历史）")
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f"生成 {created} 条模拟快照，跳过 {skipped} 条（已存在）；企业 {len(rows)} 家"))