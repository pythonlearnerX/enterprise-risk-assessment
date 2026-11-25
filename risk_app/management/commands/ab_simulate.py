# -*- coding: utf-8 -*-
"""生成模拟 A/B 流量，用于演示统计判断（数据标记 source=sim）。

真实系统上线后不需要这个命令；它只解决“课程环境没有真实用户”的问题。
"""
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from risk_app.models import ABEvent, ABExperiment


class Command(BaseCommand):
    help = "为实验生成模拟曝光/转化事件（source=sim）"

    def add_arguments(self, parser):
        parser.add_argument("--key", default="risk_export_cta", help="实验标识")
        parser.add_argument("--n", type=int, default=4000, help="每组曝光数")
        parser.add_argument("--a-rate", type=float, default=None, help="A 组真实转化率")
        parser.add_argument("--b-rate", type=float, default=None, help="B 组真实转化率")
        parser.add_argument("--seed", type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **options):
        exp = ABExperiment.objects.filter(key=options["key"]).first()
        if not exp:
            self.stderr.write("实验不存在，先运行 ab_seed")
            return
        rng = random.Random(options["seed"])
        a_rate = options["a_rate"] if options["a_rate"] is not None else exp.baseline_rate * 1.0
        b_rate = options["b_rate"] if options["b_rate"] is not None else exp.expected_rate
        n = options["n"]

        bulk = []
        for variant, rate in (("A", a_rate), ("B", b_rate)):
            for i in range(n):
                user = f"sim_{variant}_{i}"
                bulk.append(ABEvent(experiment=exp, variant=variant, user_key=user,
                                    kind="impression", source="sim"))
                if rng.random() < rate:
                    bulk.append(ABEvent(experiment=exp, variant=variant, user_key=user,
                                        kind=exp.metric, source="sim"))
        ABEvent.objects.bulk_create(bulk, batch_size=2000)

        result = exp.result()
        self.stdout.write(self.style.SUCCESS(
            f"{exp.key}：A {result['a_rate']:.3f}（{result['a_convert']}/{result['a_impression']}），"
            f"B {result['b_rate']:.3f}（{result['b_convert']}/{result['b_impression']}），"
            f"p={result['p_value']:.4f}，结论：{result['verdict_label']}"))