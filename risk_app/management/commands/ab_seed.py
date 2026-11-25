# -*- coding: utf-8 -*-
"""创建两个示例 A/B 实验。"""
from django.core.management.base import BaseCommand

from risk_app.models import ABExperiment

EXPERIMENTS = [
    {
        "key": "risk_export_cta",
        "name": "风险行情：顶部快捷导出条",
        "page": "风险行情 /risk/list/",
        "hypothesis": "在风险行情页顶部加一条“导出当前筛选结果”的醒目入口，"
                      "能降低用户找不到导出按钮的摩擦，从而提升导出转化率。",
        "metric": "export",
        "metric_label": "导出率 = 导出次数 / 页面曝光",
        "variant_a": "现状：导出按钮位于筛选表单右下",
        "variant_b": "实验：顶部新增快捷导出条（含条数与说明）",
        "ratio": 0.5,
        "baseline_rate": 0.22,
        "expected_rate": 0.27,
        "min_sample": 100,
    },
    {
        "key": "ent_list_page_size",
        "name": "企业信息：每页 10 条 vs 20 条",
        "page": "企业信息 /enterprise/list/",
        "hypothesis": "企业列表每页展示 20 条（B 组）可以减少翻页次数，"
                      "让用户更快找到目标企业，从而提升进入企业详情页的比例。",
        "metric": "detail",
        "metric_label": "详情点击率 = 进入企业详情次数 / 列表曝光",
        "variant_a": "现状：每页 10 条",
        "variant_b": "实验：每页 20 条",
        "ratio": 0.5,
        "baseline_rate": 0.18,
        "expected_rate": 0.175,
        "min_sample": 100,
    },
]


class Command(BaseCommand):
    help = "创建示例 A/B 实验（已存在则跳过）"

    def handle(self, *args, **options):
        created = 0
        for item in EXPERIMENTS:
            _, is_new = ABExperiment.objects.get_or_create(key=item["key"], defaults=item)
            created += 1 if is_new else 0
        self.stdout.write(self.style.SUCCESS(
            f"新建 {created} 个实验，当前共 {ABExperiment.objects.count()} 个"))