import json
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import AISetting, Enterprise, RiskIndicator, UserProfile


class BaseData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("admin_t", "", "admin123456")
        cls.user = User.objects.create_user("user_t", "", "user123456")
        UserProfile.objects.create(user=cls.user, role="normal", department="信贷部")
        cls.ent = Enterprise.objects.create(
            firm_name="测试企业有限公司", usc_code="91500000TEST000001",
            ope_status="1", firm_category="E", reg_cap=500)
        cls.risk = RiskIndicator.objects.create(
            enterprise=cls.ent, name=cls.ent.firm_name,
            total_risk_score=72.5, risk_level="medium",
            financial_score=70, operation_score=80,
            compliance_score=65, quality_score=75)


class AuthTests(BaseData):
    def test_login_page_ok(self):
        self.assertEqual(self.client.get(reverse("risk_app:login")).status_code, 200)

    def test_anonymous_redirected(self):
        resp = self.client.get(reverse("risk_app:enterprise_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])
        self.assertIn("next=", resp["Location"])

    def test_dashboard_by_role(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("risk_app:index")), "管理驾驶舱")
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertIn("我的工作台", html)
        self.assertNotIn("管理驾驶舱", html)

    def test_manage_users_permission(self):
        self.client.force_login(self.user)
        # 改用 admin_required：无权限给 403（未登录才是 302 跳登录）
        self.assertEqual(self.client.get(reverse("risk_app:manage_users")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("risk_app:manage_users")).status_code, 200)


class DataTests(BaseData):
    def test_scores_within_100(self):
        for r in RiskIndicator.objects.all():
            for f in ("total_risk_score", "financial_score", "operation_score",
                      "compliance_score", "quality_score"):
                self.assertLessEqual(float(getattr(r, f)), 100)
                self.assertGreaterEqual(float(getattr(r, f)), 0)

    def test_chart_apis(self):
        self.client.force_login(self.admin)
        for name, keys in [
            ("risk_app:chart_data_enterprise", {"status", "capital", "year", "total"}),
            ("risk_app:chart_data_risk", {"levels", "hist", "top", "count"}),
            ("risk_app:chart_data_analysis", {"hist", "lorentz", "gini", "corr", "residual", "cohort", "insights"}),
        ]:
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(keys.issubset(data.keys()), name)

    def test_risk_detail_has_ai_panel(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:risk_detail", args=[self.risk.pk])).content.decode()
        self.assertIn("btn-ai", html)
        self.assertIn("AI 解读", html)


class AITests(BaseData):
    def test_analyze_without_key(self):
        self.client.force_login(self.user)
        import json
        resp = self.client.post(reverse("risk_app:ai_analyze"),
                                data=json.dumps({"risk_id": self.risk.pk}),
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertFalse(body["ok"])
        self.assertTrue(body.get("need_key"))

    def test_settings_clear_key(self):
        setting = AISetting.objects.create(user=self.user, api_key="sk-test")
        self.client.force_login(self.user)
        self.client.post(reverse("risk_app:ai_settings"), {"action": "clear_key"})
        setting.refresh_from_db()
        self.assertEqual(setting.api_key, "")

class FeatureTests(BaseData):
    def test_compare_page(self):
        self.client.force_login(self.admin)
        ids = [self.ent.pk]
        resp = self.client.get(reverse("risk_app:chart_compare"), {"ids": ids})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "四维雷达对比")

    def test_csv_export(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("risk_app:risk_list"), {"export": "csv"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("综合得分", resp.content.decode("utf-8-sig"))

    def test_detail_has_percentile_and_history(self):
        from .models import RiskSnapshot
        RiskSnapshot.objects.create(enterprise=self.ent, year=2025,
                                    total_score=72.5, level="medium", note="演示模拟")
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:risk_detail", args=[self.risk.pk])).content.decode()
        self.assertIn("全库百分位", html)
        self.assertIn("chart-history", html)
        self.assertIn("模拟", html)

    def test_enterprise_list_has_compare_checkbox(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse("risk_app:enterprise_list")), 'name="ids"')


class AlertTests(BaseData):
    def test_alert_rule_lifecycle(self):
        from .models import AlertRule
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("risk_app:alerts")).status_code, 200)
        self.client.post(reverse("risk_app:alerts"), {
            "action": "add", "name": "高分预警", "metric": "total",
            "threshold": "70", "level": "",
        })
        rule = AlertRule.objects.get(user=self.user, name="高分预警")
        self.assertTrue(rule.queryset().filter(pk=self.risk.pk).exists())
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertIn("预警订阅", html)
        self.assertIn("高分预警", html)
        self.client.post(reverse("risk_app:alerts"), {"action": "delete", "rule_id": rule.pk})
        self.assertFalse(AlertRule.objects.filter(pk=rule.pk).exists())

    def test_detail_breakdown_and_share(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:risk_detail", args=[self.risk.pk])).content.decode()
        self.assertIn("chart-sunburst", html)
        self.assertIn("chart-waterfall", html)
        self.assertIn("breakdown-data", html)
        self.assertIn("btn-share", self.client.get(reverse("risk_app:chart_compare"),
                                                   {"ids": [self.ent.pk]}).content.decode())

    def test_score_consistency(self):
        from decimal import Decimal
        r = self.risk
        avg = (float(r.financial_score) + float(r.operation_score)
               + float(r.compliance_score) + float(r.quality_score)) / 4
        self.assertLessEqual(abs(avg - float(r.total_risk_score)), 0.02)


class ChartUpgradeTests(BaseData):
    def test_enterprise_chart_has_six_datasets(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("risk_app:chart_data_enterprise")).json()
        for key in ("status", "capital", "year", "orgs", "top_cap", "types"):
            self.assertIn(key, data)
        self.assertEqual(len(data["orgs"]["labels"]), len(data["orgs"]["values"]))

    def test_risk_chart_has_dims(self):
        self.client.force_login(self.user)
        data = self.client.get(reverse("risk_app:chart_data_risk")).json()
        self.assertEqual([d["name"] for d in data["dims"]], ["财务", "经营", "合规", "质量"])

    def test_compare_has_four_cards_and_table(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_compare"),
                               {"ids": [self.ent.pk]}).content.decode()
        for label in ("对比企业", "最高分", "最低分", "平均分"):
            self.assertIn(label, html)
        self.assertIn("指标对照", html)

    def test_risk_query_filters(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("risk_app:risk_list"),
                               {"score_min": "0", "score_max": "100", "keyword": self.ent.firm_name})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.ent.firm_name)


class DrilldownTests(BaseData):
    def test_dashboard_kpi_links(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertIn("stat-link", html)
        self.assertIn(reverse("risk_app:enterprise_list"), html)
        self.assertIn(reverse("risk_app:risk_list") + "?level=high", html)

    def test_enterprise_filters(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:enterprise_list"),
                               {"status": "1"}).content.decode()
        self.assertIn(self.ent.firm_name, html)

    def test_enterprise_csv(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("risk_app:enterprise_list"), {"export": "csv"})
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("统一社会信用代码", resp.content.decode("utf-8-sig"))

    def test_chart_drill_scripts(self):
        self.client.force_login(self.user)
        self.assertIn("STATUS_MAP", self.client.get(reverse("risk_app:chart_enterprise")).content.decode())
        self.assertIn("LEVEL_MAP", self.client.get(reverse("risk_app:chart_risk")).content.decode())


class RiskCalcTests(SimpleTestCase):
    def _values(self, n=1):
        return {k: n for k in ["cai_1", "cai_2", "cai_3", "s_an_1", "s_an_2", "s_an_3",
                               "li_an_1", "li_an_2", "li_an_3", "zhi_1", "zhi_2", "zhi_3"]}

    def test_count_mode_deduction(self):
        """扣分制：扣掉的分才是风险分；3 次/维 → 12 分 → 低风险（早期版本错算成 88 分）。"""
        from .risk_calc import calc_risk
        r = calc_risk(self._values(3), mode="count")
        self.assertEqual(r["dimensions"]["financial"]["score"], 3.0)
        self.assertEqual(r["dimensions"]["financial"]["safe"], 22.0)
        self.assertEqual(r["total"], 12.0)
        self.assertEqual(r["level"], "low")

    def test_count_mode_more_events_higher_risk(self):
        from .risk_calc import calc_risk
        low = calc_risk(self._values(2), mode="count")["total"]
        high = calc_risk(self._values(6), mode="count")["total"]
        self.assertGreater(high, low)

    def test_count_mode_zero_events(self):
        from .risk_calc import calc_risk
        r = calc_risk(self._values(0), mode="count")
        self.assertEqual(r["total"], 0.0)
        self.assertEqual(r["level"], "low")

    def test_points_mode(self):
        from .risk_calc import calc_risk
        r = calc_risk(self._values(25), mode="points")
        self.assertEqual(r["total"], 100.0)

    def test_no_negative(self):
        """次数再多，风险分封顶 25/维，总分封顶 100。"""
        from .risk_calc import calc_risk
        r = calc_risk(self._values(100), mode="count")
        self.assertEqual(r["dimensions"]["financial"]["score"], 25.0)
        self.assertEqual(r["total"], 100.0)

    def test_year_weights(self):
        from .risk_calc import calc_risk
        values = self._values(0)
        values.update({"cai_1": 0, "cai_2": 0, "cai_3": 30})
        r = calc_risk(values, mode="count", year_weights=(1, 0, 0))
        # 只取近 1 年（=0 次），所以该维风险分 0；近 3 年的 30 次不参与
        self.assertEqual(r["dimensions"]["financial"]["score"], 0.0)

    def test_invalid_mode(self):
        from .risk_calc import calc_risk
        with self.assertRaises(ValueError):
            calc_risk(self._values(1), mode="bad")


class ReportPdfTests(BaseData):
    def test_pdf_export(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("risk_app:enterprise_report_pdf", args=[self.ent.pk]))
        self.assertEqual(resp.status_code, 200)
        data = b"".join(resp.streaming_content)
        self.assertTrue(data.startswith(b"%PDF"))
        self.assertGreater(len(data), 8000)
        disp = resp.get("Content-Disposition", "")
        self.assertIn("filename*=utf-8", disp)
        self.assertIn(".pdf", disp)

    def test_csv_names(self):
        self.client.force_login(self.user)
        r1 = self.client.get(reverse("risk_app:risk_list"), {"export": "csv"})
        self.assertIn("risk_list_", r1["Content-Disposition"])
        r2 = self.client.get(reverse("risk_app:enterprise_list"), {"export": "csv"})
        self.assertIn("enterprise_list_", r2["Content-Disposition"])


class ABStatTests(SimpleTestCase):
    def test_bucket_stable_and_spread(self):
        from .abtest import bucket
        self.assertEqual(bucket("u1", "exp"), bucket("u1", "exp"))
        diff = sum(1 for i in range(200) if bucket(f"u{i}", "exp1") != bucket(f"u{i}", "exp2"))
        self.assertGreater(diff, 40, "不同实验应基本独立")
        b = sum(1 for i in range(2000) if bucket(f"u{i}", "exp") == "B")
        self.assertTrue(800 < b < 1200, f"分组不均衡：B={b}/2000")

    def test_proportion_test_significant(self):
        from .abtest import proportion_test
        r = proportion_test(220, 1000, 270, 1000)
        self.assertAlmostEqual(r["a_rate"], 0.22, places=4)
        self.assertAlmostEqual(r["b_rate"], 0.27, places=4)
        self.assertTrue(r["significant"])
        self.assertLess(r["p_value"], 0.05)
        self.assertGreater(r["ci_low"], 0)

    def test_proportion_test_not_significant(self):
        from .abtest import proportion_test
        r = proportion_test(180, 1000, 178, 1000)
        self.assertFalse(r["significant"])

    def test_sample_size(self):
        from .abtest import required_sample_size
        n = required_sample_size(0.22, 0.27)
        # 5pp 提升、alpha=.05、power=.8 → 每组约 1160
        self.assertTrue(1000 < n < 1300, n)

    def test_decide(self):
        from .abtest import decide
        self.assertEqual(decide(220, 1000, 270, 1000)["verdict"], "ship_b")
        self.assertEqual(decide(270, 1000, 220, 1000)["verdict"], "keep_a")
        self.assertEqual(decide(5, 20, 6, 20)["verdict"], "continue")
        self.assertEqual(decide(180, 1000, 178, 1000)["verdict"], "continue")


class ABFlowTests(BaseData):
    def _exp(self):
        from .models import ABExperiment
        return ABExperiment.objects.create(
            key="risk_export_cta", name="测试实验", metric="export",
            metric_label="导出率", baseline_rate=0.2, expected_rate=0.25,
            min_sample=10, status="running")

    def test_assignment_is_stable(self):
        exp = self._exp()
        v1 = exp.assign("u9")
        v2 = exp.assign("u9")
        self.assertEqual(v1, v2)
        self.assertIn(v1, ("A", "B"))

    def test_impression_dedup_and_conversion(self):
        from .models import ABEvent
        exp = self._exp()
        self.client.force_login(self.user)
        self.client.get(reverse("risk_app:risk_list"))
        self.client.get(reverse("risk_app:risk_list"))
        impressions = ABEvent.objects.filter(experiment=exp, kind="impression").count()
        self.assertEqual(impressions, 1, "同一天重复访问只记一次曝光")
        self.client.get(reverse("risk_app:risk_list"), {"export": "csv"})
        self.assertEqual(ABEvent.objects.filter(experiment=exp, kind="export").count(), 1)

    def test_dashboard_and_detail(self):
        exp = self._exp()
        # A/B 已改为仅管理员（普通用户侧栏也不再显示）
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("risk_app:ab_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("risk_app:ab_detail", args=[exp.pk])).status_code, 200)

    def test_toggle_requires_admin(self):
        exp = self._exp()
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("risk_app:ab_toggle", args=[exp.pk]),
                                          {"action": "toggle"}).status_code, 403)
        self.client.force_login(self.admin)
        self.client.post(reverse("risk_app:ab_toggle", args=[exp.pk]), {"action": "toggle"})
        exp.refresh_from_db()
        self.assertEqual(exp.status, "stopped")


class DataSyncTests(BaseData):
    """图表的数必须跟着分数变——这是一次真实回归。"""

    def test_level_follows_score(self):
        from .models import RiskIndicator
        r = RiskIndicator.objects.get(pk=self.risk.pk)
        r.total_risk_score = 55
        r.save()
        r.refresh_from_db()
        self.assertEqual(r.risk_level, "low")
        r.total_risk_score = 85
        r.save()
        r.refresh_from_db()
        self.assertEqual(r.risk_level, "high")

    def test_chart_api_reflects_change_immediately(self):
        from .models import RiskIndicator
        self.client.force_login(self.user)
        before = self.client.get(reverse("risk_app:chart_data_risk")).json()["high"]
        r = RiskIndicator.objects.get(pk=self.risk.pk)
        r.total_risk_score = 95
        r.save()
        after = self.client.get(reverse("risk_app:chart_data_risk")).json()["high"]
        self.assertNotEqual(before, after, "分数变了，图表数据必须立刻变（不能有缓存）")

    def test_recalculate_from_items(self):
        from .models import RiskIndicator
        r = RiskIndicator.objects.get(pk=self.risk.pk)
        # 12 项共 150 → 总分 150/3 = 50
        for f in ("cai_1", "cai_2", "cai_3", "s_an_1", "s_an_2", "s_an_3"):
            setattr(r, f, 25)
        for f in ("li_an_1", "li_an_2", "li_an_3", "zhi_1", "zhi_2", "zhi_3"):
            setattr(r, f, 0)
        r.recalculate(from_items=True)
        r.save()
        self.assertAlmostEqual(float(r.total_risk_score), 50.0, places=1)
        self.assertEqual(float(r.financial_score), 100.0)


class AnalyticsTests(BaseData):
    def test_build_keys(self):
        from . import analytics
        d = analytics.build()
        for key in ("hist", "lorentz", "bands", "corr", "residual", "radar",
                    "scatter", "cohort", "insights", "gini"):
            self.assertIn(key, d)
        self.assertGreaterEqual(len(d["insights"]), 5)
        self.assertTrue(0 <= d["gini"] <= 1)

    def test_analysis_page_and_api(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("risk_app:chart_analysis")).status_code, 200)
        data = self.client.get(reverse("risk_app:chart_data_analysis")).json()
        self.assertEqual(data["n"], 1)


class AIInsightTests(BaseData):
    def test_explain_without_key(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("risk_app:ai_explain"),
                                data=json.dumps({"scope": "chart_risk", "target": "level"}),
                                content_type="application/json")
        data = resp.json()
        self.assertFalse(data["ok"])
        self.assertTrue(data.get("need_key"))

    def test_explain_saves_insight(self):
        from unittest.mock import patch

        from .models import AISetting, AIInsight
        AISetting.objects.create(user=self.user, provider="custom",
                                 base_url="http://127.0.0.1:9/v1", model_name="m",
                                 api_key="sk-test")
        self.client.force_login(self.user)
        with patch("risk_app.ai_service.explain", return_value=("1) 现象\n2) 原因\n3) 建议", None)):
            resp = self.client.post(reverse("risk_app:ai_explain"),
                                    data=json.dumps({"scope": "compare",
                                                     "target": str(self.ent.pk)}),
                                    content_type="application/json")
        self.assertTrue(resp.json()["ok"])
        row = AIInsight.objects.get(user=self.user)
        self.assertEqual(row.scope, "compare")
        self.assertIn("现象", row.answer)

    def test_insight_admin_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("risk_app:ai_insights")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("risk_app:ai_insights")).status_code, 200)

    def test_buttons_rendered(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_enterprise")).content.decode()
        self.assertEqual(html.count("data-ai-explain"), 6)
        html2 = self.client.get(reverse("risk_app:chart_compare"),
                                {"ids": [self.ent.pk]}).content.decode()
        self.assertIn("AI 解读对比", html2)


class MapTests(BaseData):
    def test_map_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("risk_app:chart_map"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "重庆企业分布地图")

    def test_map_api(self):
        from .models import Enterprise
        Enterprise.objects.filter(pk=self.ent.pk).update(district="500107")
        self.client.force_login(self.user)
        data = self.client.get(reverse("risk_app:chart_data_map")).json()
        self.assertIn("rows", data)
        row = next((r for r in data["rows"] if r["code"] == "500107"), None)
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "九龙坡区")
        self.assertEqual(row["count"], 1)

    def test_district_filter(self):
        from .models import Enterprise
        Enterprise.objects.filter(pk=self.ent.pk).update(district="500107")
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:enterprise_list"),
                               {"district": "500107"}).content.decode()
        self.assertIn(self.ent.firm_name, html)
        self.assertIn("区县：九龙坡区", html)


class MenuPermissionTests(BaseData):
    """图1：菜单管理 + 分级权限管理。"""

    def test_admin_sees_manage_menu(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertIn("管理后台", html)
        self.assertIn("用户管理", html)
        self.assertIn("AI 解读记录", html)

    def test_normal_user_has_no_manage_menu(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertNotIn("管理后台", html)
        self.assertNotIn(">用户管理<", html)
        self.assertIn("企业信息", html)

    def test_active_class_present(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:enterprise_list")).content.decode()
        self.assertIn('class="nav-link active" href="/enterprise/list/"', html)

    def test_console_admin_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("risk_app:console")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("risk_app:console")).status_code, 200)

    def test_console_anonymous_redirects(self):
        resp = self.client.get(reverse("risk_app:console"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_admin_required_decorator_on_users(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("risk_app:manage_users")).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("risk_app:manage_users")).status_code, 200)

    def test_403_page_content(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:console")).content.decode()
        self.assertIn("403", html)
        self.assertIn("没有访问权限", html)


class ComparePickerTests(BaseData):
    """企业对比页内直接选择企业。"""

    def test_candidates_recommended(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_compare")).content.decode()
        self.assertIn("选择对比企业", html)
        self.assertIn("添加", html)

    def test_add_via_ids(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_compare"),
                               {"ids": [self.ent.pk]}).content.decode()
        self.assertIn(self.ent.firm_name, html)
        self.assertIn("至少选择 2 家", html)

    def test_remove_link(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_compare"),
                               {"ids": [self.ent.pk]}).content.decode()
        self.assertIn("移除", html)

    def test_search_filter(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_compare"),
                               {"q": "不存在的公司名"}).content.decode()
        self.assertIn("没有匹配的企业", html)

    def test_ids_multi_value(self):
        """企业列表勾选提交的是 ?ids=1&ids=2（多值），旧代码只读第一个 → 只能对比 1 家。"""
        from .models import Enterprise
        other = Enterprise.objects.create(firm_name="测试企业B", usc_code="91500000TEST0002",
                                          reg_cap=100, ope_status="1", province="500000")
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_compare"),
                               {"ids": [self.ent.pk, other.pk]}).content.decode()
        self.assertIn(self.ent.firm_name, html)
        self.assertIn("测试企业B", html)

    def test_ids_accepts_comma_and_duplicates(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("risk_app:chart_compare"),
                               {"ids": f"{self.ent.pk},{self.ent.pk}"})
        self.assertEqual(resp.status_code, 200)


class HomeMergeTests(BaseData):
    """首页合并重庆地图 + 三块分区 + 每图 AI 按钮 + A/B 仅管理员。"""

    def test_home_has_three_sections(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertIn("一、数据概览", html)
        self.assertIn("二、风险画像", html)
        self.assertIn("三、重庆地域分布", html)

    def test_home_has_map_and_charts(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertEqual(html.count("data-ai-explain"), 3)
        self.assertIn('id="home-map"', html)
        self.assertIn('id="home-level"', html)

    def test_analysis_every_chart_has_ai(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:chart_analysis")).content.decode()
        self.assertEqual(html.count("chart-box"), 8)
        self.assertEqual(html.count("data-ai-explain"), 8)

    def test_ab_hidden_for_normal_user(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertNotIn("A/B 实验", html)
        self.assertEqual(self.client.get(reverse("risk_app:ab_dashboard")).status_code, 403)

    def test_ab_visible_for_admin(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        self.assertIn("A/B 实验", html)
        self.assertEqual(self.client.get(reverse("risk_app:ab_dashboard")).status_code, 200)

    def test_map_menu_removed(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse("risk_app:index")).content.decode()
        # 菜单项已去掉，但地图页路由仍保留
        self.assertNotIn('href="/chart/map/"', html.split("</aside>")[0])
        self.assertEqual(self.client.get(reverse("risk_app:chart_map")).status_code, 200)


class LocalModelTests(BaseData):
    """项目 15：本地 NLP 微服务集成（页面、降级、转换、高亮转义）。"""

    def test_page_renders(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("risk_app:model_show"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "本地模型识别")
        self.assertContains(resp, "待分析文本")

    def test_analyze_requires_login(self):
        resp = self.client.post(reverse("risk_app:model_analyze"),
                                data=json.dumps({"text": "亏损"}), content_type="application/json")
        self.assertEqual(resp.status_code, 302)

    def test_degrade_when_service_down(self):
        """服务未启动：返回 code=1 与可操作提示，而不是 500。"""
        from unittest.mock import patch
        self.client.force_login(self.user)
        with patch("risk_app.nlp_infer.call_nlp_service", return_value=None):
            resp = self.client.post(reverse("risk_app:model_analyze"),
                                    data=json.dumps({"text": "公司亏损"}),
                                    content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["code"], 1)
        self.assertIn("未启动", body["message"])

    def test_empty_text(self):
        self.client.force_login(self.user)
        body = self.client.post(reverse("risk_app:model_analyze"),
                                data=json.dumps({"text": "   "}),
                                content_type="application/json").json()
        self.assertEqual(body["code"], 1)
        self.assertIn("文本为空", body["message"])

    def test_convert_and_highlight(self):
        from unittest.mock import patch
        fake = {
            "total_score": 63.0, "risk_level": "high", "keywords_found": 2,
            "details": {
                "financial": {"score": 10, "keywords": ["财务造假"], "count": 1},
                "operation": {"score": 0, "keywords": [], "count": 0},
                "compliance": {"score": 55, "keywords": ["证监会", "立案调查"], "count": 2},
                "public_opinion": {"score": 0, "keywords": [], "count": 0},
            },
        }
        self.client.force_login(self.user)
        with patch("risk_app.nlp_infer.call_nlp_service", return_value=fake):
            body = self.client.post(reverse("risk_app:model_analyze"),
                                    data=json.dumps({"text": "涉嫌财务造假，被证监会立案调查"}),
                                    content_type="application/json").json()
        self.assertEqual(body["code"], 0)
        d = body["data"]
        self.assertEqual(d["total_score"], 63.0)
        self.assertEqual(d["level_label"], "高风险")
        self.assertEqual(d["compliance_score"], 55)
        self.assertEqual(d["keywords"]["合规"], ["证监会", "立案调查"])
        self.assertIn('class="nlp-hit"', d["highlighted_text"])

    def test_highlight_no_nested_tags(self):
        """「行政处罚」与「处罚」不能叠加成嵌套标签。"""
        from unittest.mock import patch
        fake = {"total_score": 20, "risk_level": "low", "keywords_found": 2,
                "details": {k: {"score": 0, "keywords": [], "count": 0}
                            for k in ("financial", "operation", "compliance", "public_opinion")}}
        fake["details"]["compliance"] = {"score": 18, "keywords": ["行政处罚", "处罚"], "count": 2}
        self.client.force_login(self.user)
        with patch("risk_app.nlp_infer.call_nlp_service", return_value=fake):
            body = self.client.post(reverse("risk_app:model_analyze"),
                                    data=json.dumps({"text": "公司受到行政处罚"}),
                                    content_type="application/json").json()
        html = body["data"]["highlighted_text"]
        self.assertIn('<b class="nlp-hit">行政处罚</b>', html)
        self.assertEqual(html.count("<b"), 1, html)

    def test_highlight_escapes_html(self):
        """输入里的 HTML 必须先转义，不能原样进页面（防 XSS）。"""
        from unittest.mock import patch
        fake = {"total_score": 10, "risk_level": "low", "keywords_found": 1,
                "details": {k: {"score": 0, "keywords": [], "count": 0}
                            for k in ("financial", "operation", "compliance", "public_opinion")}}
        fake["details"]["financial"] = {"score": 10, "keywords": ["亏损"], "count": 1}
        self.client.force_login(self.user)
        with patch("risk_app.nlp_infer.call_nlp_service", return_value=fake):
            body = self.client.post(reverse("risk_app:model_analyze"),
                                    data=json.dumps({"text": "<script>alert(1)</script>公司亏损"}),
                                    content_type="application/json").json()
        html = body["data"]["highlighted_text"]
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("nlp-hit", html)
