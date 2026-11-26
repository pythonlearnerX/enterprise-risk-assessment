from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Enterprise(models.Model):
    """企业基础信息（对应设计文档 enterprise 表，24 个字段）。"""

    CATEGORY_CHOICES = [("E", "企业"), ("P", "个体户")]
    STATUS_CHOICES = [("1", "在营"), ("2", "注销"), ("3", "吊销")]

    firm_eid = models.CharField("企业EID", max_length=64, unique=True, null=True, blank=True)
    usc_code = models.CharField("统一社会信用代码", max_length=18, unique=True, null=True, blank=True)
    firm_name = models.CharField("企业名称", max_length=200, db_index=True)
    legal_rep = models.CharField("法定代表人", max_length=50, null=True, blank=True, db_index=True)
    firm_type = models.CharField("企业类型", max_length=50, null=True, blank=True)
    firm_category = models.CharField("企业类别", max_length=10, choices=CATEGORY_CHOICES,
                                     null=True, blank=True)
    ope_status = models.CharField("经营状态", max_length=10, choices=STATUS_CHOICES,
                                  null=True, blank=True, db_index=True)
    est_date = models.DateField("成立日期", null=True, blank=True)
    cancel_date = models.DateField("注销日期", null=True, blank=True)
    reg_cap = models.DecimalField("注册资本(万元)", max_digits=20, decimal_places=6,
                                  null=True, blank=True)
    reg_cap_cur = models.CharField("注册资本币种", max_length=20, null=True, blank=True)
    rec_cap = models.DecimalField("实收资本", max_digits=20, decimal_places=6,
                                  null=True, blank=True)
    emp_num = models.IntegerField("员工人数", null=True, blank=True)
    province = models.CharField("省份", max_length=20, null=True, blank=True)
    city = models.CharField("城市", max_length=20, null=True, blank=True)
    district = models.CharField("区县", max_length=20, null=True, blank=True)
    reg_org = models.CharField("登记机关", max_length=200, null=True, blank=True)
    appr_date = models.DateField("核准日期", null=True, blank=True)
    ope_period = models.CharField("营业期限", max_length=100, null=True, blank=True)
    reg_address = models.CharField("注册地址", max_length=500, null=True, blank=True)
    ope_address = models.CharField("经营地址", max_length=500, null=True, blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "enterprise"
        verbose_name = "企业基础信息"
        verbose_name_plural = verbose_name
        ordering = ["-update_time"]

    def __str__(self):
        return self.firm_name


class RiskIndicator(models.Model):
    """风险指标（12 项原始指标 + 四维与综合得分）。"""

    LEVEL_CHOICES = [("low", "低风险"), ("medium", "中风险"), ("high", "高风险")]

    enterprise = models.ForeignKey(Enterprise, on_delete=models.CASCADE,
                                   related_name="risk_indicators", verbose_name="所属企业")
    name = models.CharField("企业名称", max_length=200, db_index=True, blank=True)

    cai_1 = models.DecimalField("近1年被裁判次数", max_digits=5, decimal_places=2, default=0)
    cai_2 = models.DecimalField("近2年被裁判次数", max_digits=5, decimal_places=2, default=0)
    cai_3 = models.DecimalField("近3年被裁判次数", max_digits=5, decimal_places=2, default=0)
    s_an_1 = models.DecimalField("近1年立案数", max_digits=5, decimal_places=2, default=0)
    s_an_2 = models.DecimalField("近2年立案数", max_digits=5, decimal_places=2, default=0)
    s_an_3 = models.DecimalField("近3年立案数", max_digits=5, decimal_places=2, default=0)
    li_an_1 = models.DecimalField("近1年被立案次数", max_digits=5, decimal_places=2, default=0)
    li_an_2 = models.DecimalField("近2年被立案次数", max_digits=5, decimal_places=2, default=0)
    li_an_3 = models.DecimalField("近3年被立案次数", max_digits=5, decimal_places=2, default=0)
    zhi_1 = models.DecimalField("近1年被执行次数", max_digits=5, decimal_places=2, default=0)
    zhi_2 = models.DecimalField("近2年被执行次数", max_digits=5, decimal_places=2, default=0)
    zhi_3 = models.DecimalField("近3年被执行次数", max_digits=5, decimal_places=2, default=0)

    financial_score = models.DecimalField("财务风险得分", max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    operation_score = models.DecimalField("经营风险得分", max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    compliance_score = models.DecimalField("合规风险得分", max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    quality_score = models.DecimalField("质量风险得分", max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_risk_score = models.DecimalField("综合得分", max_digits=5, decimal_places=2,
                                           default=0, db_index=True,
                                           validators=[MinValueValidator(0), MaxValueValidator(100)])
    risk_level = models.CharField("风险等级", max_length=10, choices=LEVEL_CHOICES, default="low")
    risk_description = models.TextField("风险说明", null=True, blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "risk_indicator"
        verbose_name = "风险指标"
        verbose_name_plural = verbose_name
        ordering = ["-total_risk_score"]


    # ---- 评分一致性：总分变了，等级必须跟着变 ----
    ITEM_FIELDS = ("cai_1", "cai_2", "cai_3", "s_an_1", "s_an_2", "s_an_3",
                   "li_an_1", "li_an_2", "li_an_3", "zhi_1", "zhi_2", "zhi_3")

    def level_of(self, score):
        return "low" if float(score) < 60 else ("medium" if float(score) < 80 else "high")

    def recalculate(self, from_items=False):
        """统一按评分函数重算等级；from_items=True 时连同四维与总分一起重算。"""
        from .risk_calc import calc_risk

        if from_items:
            values = {f: float(getattr(self, f)) for f in self.ITEM_FIELDS}
            res = calc_risk(values, mode="points")
            self.financial_score = round(res["dimensions"]["financial"]["score"] * 4, 2)
            self.operation_score = round(res["dimensions"]["operation"]["score"] * 4, 2)
            self.compliance_score = round(res["dimensions"]["compliance"]["score"] * 4, 2)
            self.quality_score = round(res["dimensions"]["quality"]["score"] * 4, 2)
            self.total_risk_score = res["total"]
        self.total_risk_score = min(100, max(0, float(self.total_risk_score or 0)))
        self.risk_level = self.level_of(self.total_risk_score)

    def save(self, *args, **kwargs):
        if not kwargs.get("_skip_sync"):
            self.recalculate(from_items=kwargs.pop("_from_items", False))
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.total_risk_score}"


class UserProfile(models.Model):
    """用户扩展信息，与 auth_user 一对一。"""

    ROLE_CHOICES = [("admin", "管理员"), ("normal", "普通用户")]

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE,
                                related_name="profile", verbose_name="关联用户")
    role = models.CharField("角色", max_length=10, choices=ROLE_CHOICES, default="normal")
    department = models.CharField("部门", max_length=50, null=True, blank=True)
    phone = models.CharField("联系电话", max_length=20, null=True, blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "user_profile"
        verbose_name = "用户扩展信息"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class AuditLog(models.Model):
    """审计日志：谁、何时、对什么对象、做了什么。"""

    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True,
                             verbose_name="操作人")
    action = models.CharField("动作", max_length=50)
    target = models.CharField("操作对象", max_length=100, null=True, blank=True)
    ip = models.CharField("客户端 IP", max_length=45, null=True, blank=True)
    detail = models.TextField("变更摘要", null=True, blank=True)
    create_time = models.DateTimeField("发生时间", auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        verbose_name = "审计日志"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]
        indexes = [models.Index(fields=["user", "create_time"], name="idx_user_time")]

    def __str__(self):
        return f"{self.action} {self.target}"

class AISetting(models.Model):
    """用户级 AI 平台配置：用自己的 API Key 调用大模型。"""

    PROVIDER_CHOICES = [
        ("deepseek", "DeepSeek"),
        ("openai", "OpenAI"),
        ("custom", "自定义（OpenAI 兼容）"),
    ]

    user = models.OneToOneField("auth.User", on_delete=models.CASCADE,
                                related_name="ai_setting", verbose_name="所属用户")
    provider = models.CharField("平台", max_length=20, choices=PROVIDER_CHOICES, default="deepseek")
    base_url = models.CharField("接口地址", max_length=200, default="https://api.deepseek.com/v1")
    model_name = models.CharField("模型名称", max_length=80, default="deepseek-chat")
    api_key = models.CharField("API Key", max_length=200, blank=True)
    enabled = models.BooleanField("启用", default=True)
    update_time = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "ai_setting"
        verbose_name = "AI 平台配置"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.user.username} · {self.provider}"


class RiskSnapshot(models.Model):
    """企业年度评分快照。

    当前数据集是单期快照，没有真实历史；演示数据由 seed_demo_history 生成并标注“模拟”，
    页面上会明确区分，避免把模拟值当成真实统计。
    """

    enterprise = models.ForeignKey(Enterprise, on_delete=models.CASCADE,
                                   related_name="snapshots", verbose_name="企业")
    year = models.PositiveSmallIntegerField("年份", db_index=True)
    total_score = models.DecimalField("综合得分", max_digits=5, decimal_places=2,
                                      validators=[MinValueValidator(0), MaxValueValidator(100)])
    level = models.CharField("风险等级", max_length=10, choices=[("low", "低风险"),
                                                                 ("medium", "中风险"),
                                                                 ("high", "高风险")], default="low")
    note = models.CharField("数据说明", max_length=50, blank=True)
    create_time = models.DateTimeField("写入时间", auto_now_add=True)

    class Meta:
        db_table = "risk_snapshot"
        verbose_name = "企业年度评分"
        verbose_name_plural = verbose_name
        unique_together = (("enterprise", "year"),)
        ordering = ["year"]

    def __str__(self):
        return f"{self.enterprise.firm_name} {self.year}: {self.total_score}"


class AlertRule(models.Model):
    """预警订阅：某指标越过阈值时在首页提示。"""

    METRIC_CHOICES = [
        ("total", "综合得分"),
        ("financial", "财务风险"),
        ("operation", "经营风险"),
        ("compliance", "合规风险"),
        ("quality", "质量风险"),
    ]
    LEVEL_CHOICES = [("", "不限等级"), ("high", "仅高风险"), ("medium", "中风险及以上")]

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE,
                             related_name="alert_rules", verbose_name="订阅人")
    name = models.CharField("规则名称", max_length=50)
    metric = models.CharField("监控指标", max_length=20, choices=METRIC_CHOICES, default="total")
    threshold = models.DecimalField("阈值（≥）", max_digits=5, decimal_places=2, default=80,
                                    validators=[MinValueValidator(0), MaxValueValidator(100)])
    level = models.CharField("等级限定", max_length=10, choices=LEVEL_CHOICES, blank=True, default="")
    enabled = models.BooleanField("启用", default=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "alert_rule"
        verbose_name = "预警规则"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.user.username} · {self.name}"

    def queryset(self):
        """返回命中的风险记录。"""
        field = {
            "total": "total_risk_score",
            "financial": "financial_score",
            "operation": "operation_score",
            "compliance": "compliance_score",
            "quality": "quality_score",
        }[self.metric]
        qs = RiskIndicator.objects.filter(**{f"{field}__gte": self.threshold})
        if self.level == "high":
            qs = qs.filter(risk_level="high")
        elif self.level == "medium":
            qs = qs.filter(risk_level__in=["high", "medium"])
        return qs


class ABExperiment(models.Model):
    """A/B 实验：一个假设 + 一个主指标 + 两组流量。"""

    STATUS_CHOICES = [("draft", "草稿"), ("running", "进行中"), ("stopped", "已停止")]
    key = models.SlugField("实验标识", max_length=50, unique=True)
    name = models.CharField("实验名称", max_length=80)
    page = models.CharField("所在页面", max_length=80, blank=True)
    hypothesis = models.TextField("实验假设", blank=True)
    metric = models.CharField("主指标（事件名）", max_length=30, default="convert")
    metric_label = models.CharField("指标说明", max_length=80, blank=True)
    variant_a = models.CharField("A 组（对照）", max_length=60, default="现状")
    variant_b = models.CharField("B 组（实验）", max_length=60, default="新方案")
    ratio = models.FloatField("B 组流量占比", default=0.5)
    baseline_rate = models.FloatField("A 组预估转化率", default=0.2)
    expected_rate = models.FloatField("B 组期望转化率", default=0.25)
    min_sample = models.PositiveIntegerField("每组最小样本", default=100)
    status = models.CharField("状态", max_length=10, choices=STATUS_CHOICES, default="running")
    decision = models.CharField("结论", max_length=20, blank=True)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        db_table = "ab_experiment"
        verbose_name = "A/B 实验"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return self.name

    @property
    def ratio_pct(self):
        """B 组流量占比（百分数，便于模板显示）。"""
        return int(round(self.ratio * 100))

    def assign(self, user_key):
        """取该用户的实验分组，首次访问时随机并落库。"""
        from . import abtest

        row = ABAssignment.objects.filter(experiment=self, user_key=user_key).first()
        if row:
            return row.variant
        variant = abtest.bucket(user_key, self.key, self.ratio)
        ABAssignment.objects.get_or_create(
            experiment=self, user_key=user_key, defaults={"variant": variant})
        return variant

    def track(self, user_key, kind, source="real"):
        """记一条事件；kind=impression 为曝光，kind=metric 为主指标转化。"""
        variant = self.assign(user_key)
        return ABEvent.objects.create(experiment=self, variant=variant,
                                      user_key=user_key, kind=kind, source=source)

    def counts(self, source=None):
        from django.db.models import Count

        qs = ABEvent.objects.filter(experiment=self)
        if source:
            qs = qs.filter(source=source)
        rows = qs.values("variant", "kind").annotate(n=Count("id"))
        data = {"A": {"impression": 0, self.metric: 0},
                "B": {"impression": 0, self.metric: 0}}
        for r in rows:
            kind = "impression" if r["kind"] == "impression" else self.metric
            if r["variant"] in data and kind in data[r["variant"]]:
                data[r["variant"]][kind] += r["n"]
        return data

    def result(self, source=None):
        """返回统计结果 + 决策建议。"""
        from . import abtest

        c = self.counts(source)
        a_n, b_n = c["A"]["impression"], c["B"]["impression"]
        res = abtest.decide(c["A"][self.metric], a_n, c["B"][self.metric], b_n,
                            min_sample=self.min_sample)
        res["a_impression"], res["b_impression"] = a_n, b_n
        res["a_convert"], res["b_convert"] = c["A"][self.metric], c["B"][self.metric]
        res["need"] = abtest.required_sample_size(self.baseline_rate, self.expected_rate)
        return res


class ABAssignment(models.Model):
    """用户分组结果（同一用户在同一实验里固定）。"""

    experiment = models.ForeignKey(ABExperiment, on_delete=models.CASCADE,
                                   related_name="assignments", verbose_name="实验")
    user_key = models.CharField("用户标识", max_length=80)
    variant = models.CharField("分组", max_length=2)
    create_time = models.DateTimeField("分桶时间", auto_now_add=True)

    class Meta:
        db_table = "ab_assignment"
        verbose_name = "A/B 分组"
        verbose_name_plural = verbose_name
        unique_together = (("experiment", "user_key"),)

    def __str__(self):
        return f"{self.experiment.key}:{self.user_key}={self.variant}"


class ABEvent(models.Model):
    """曝光 / 转化事件。source=sim 表示模拟数据，页面会标注。"""

    SOURCE_CHOICES = [("real", "真实"), ("sim", "模拟")]

    experiment = models.ForeignKey(ABExperiment, on_delete=models.CASCADE,
                                   related_name="events", verbose_name="实验")
    variant = models.CharField("分组", max_length=2)
    user_key = models.CharField("用户标识", max_length=80)
    kind = models.CharField("事件", max_length=30)
    source = models.CharField("来源", max_length=10, choices=SOURCE_CHOICES, default="real")
    create_time = models.DateTimeField("发生时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ab_event"
        verbose_name = "A/B 事件"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]
        indexes = [models.Index(fields=["experiment", "variant", "kind"])]

    def __str__(self):
        return f"{self.experiment.key}/{self.variant}/{self.kind}"


class AIInsight(models.Model):
    """AI 解读记录：用户点“AI 解读”后生成，管理员可集中查看。"""

    SCOPE_CHOICES = [
        ("compare", "企业对比"),
        ("chart_enterprise", "企业可视化"),
        ("chart_risk", "风险可视化"),
        ("chart_analysis", "分析看板"),
        ("risk_detail", "风险详情"),
    ]

    user = models.ForeignKey("auth.User", on_delete=models.CASCADE,
                             related_name="ai_insights", verbose_name="发起人")
    scope = models.CharField("页面", max_length=30, choices=SCOPE_CHOICES)
    target = models.CharField("对象", max_length=120, blank=True)
    title = models.CharField("标题", max_length=120, blank=True)
    facts = models.TextField("输入事实", blank=True)
    answer = models.TextField("解读结果", blank=True)
    model_name = models.CharField("模型", max_length=80, blank=True)
    ok = models.BooleanField("是否成功", default=True)
    error = models.CharField("错误信息", max_length=200, blank=True)
    create_time = models.DateTimeField("生成时间", auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ai_insight"
        verbose_name = "AI 解读记录"
        verbose_name_plural = verbose_name
        ordering = ["-create_time"]

    def __str__(self):
        return f"{self.get_scope_display()} · {self.user.username}"
