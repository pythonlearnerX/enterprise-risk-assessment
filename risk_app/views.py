import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Q
from django.http import FileResponse, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from . import abtest, ai_service, analytics, charts, llm_predict, nlp_infer, risk_calc
from .decorators import admin_required, is_admin
from .models import (ABEvent, ABExperiment, AIInsight, AISetting, AlertRule,
                     AuditLog, Enterprise, RiskIndicator)

STATUS = {"1": "在营", "2": "注销", "3": "吊销"}
LEVEL = {"low": "低风险", "medium": "中风险", "high": "高风险"}
CITY_TOP = 10
SCORE_BINS = [("0-19", 0, 20), ("20-39", 20, 40), ("40-59", 40, 60),
              ("60-79", 60, 80), ("80-100", 80, 101)]




# ---------------------------------------------------------------------------
# A/B 测试埋点
# ---------------------------------------------------------------------------
def _user_key(request):
    return f"u{request.user.id}"


def _ab_experiment(key):
    return ABExperiment.objects.filter(key=key, status="running").first()


def _ab_impression(request, key):
    """曝光：同一用户同一天只记一次，避免刷新灌水。成功后返回分组。"""
    exp = _ab_experiment(key)
    if not exp:
        return None
    today = __import__("datetime").date.today().isoformat()
    flag = f"ab_seen_{exp.key}_{today}"
    variant = exp.assign(_user_key(request))
    if not request.session.get(flag):
        ABEvent.objects.create(experiment=exp, variant=variant,
                               user_key=_user_key(request), kind="impression")
        request.session[flag] = True
    return variant


def _ab_convert(request, key):
    """转化：主指标事件。"""
    exp = _ab_experiment(key)
    if not exp:
        return None
    variant = exp.assign(_user_key(request))
    ABEvent.objects.create(experiment=exp, variant=variant,
                           user_key=_user_key(request), kind=exp.metric)
    return variant


@login_required
def index(request):
    """首页：展示已入库的企业与风险记录数量，验证“路由→视图→模型→模板”链路。"""
    context = {"error": None}
    try:
        context["enterprise_count"] = Enterprise.objects.count()
        context["risk_count"] = RiskIndicator.objects.count()
        context["high_count"] = RiskIndicator.objects.filter(risk_level="high").count()
        context["top_risks"] = list(
            RiskIndicator.objects.order_by("-total_risk_score")[:5]
            .values("id", "name", "total_risk_score", "risk_level"))
        setting = getattr(request.user, "ai_setting", None)
        context["ai_ready"] = bool(setting and setting.api_key)
        context["ai_model"] = setting.model_name if setting else ""
        if request.user.is_superuser:
            context["user_count"] = User.objects.count()
            context["admin_count"] = User.objects.filter(is_superuser=True).count()
        # 首页第二块：风险画像（等级 + 得分分布）
        context["levels"] = _level_counts()
        context["hist"] = _score_hist()
        # 首页第三块：重庆地图（合并自原 /chart/map/）
        rows = _map_rows()
        context["map_rows"] = rows[:6]
        context["map_total"] = sum(r["count"] for r in rows)
        context["map_districts"] = len(rows)
        # 注意：这里传 list，模板用 json_script 序列化；传 json 字符串会被再转义一次
        context["map_data"] = [{"name": r["name"], "value": r["count"],
                                "high": r["high"], "rate": r["high_rate"],
                                "code": r["code"]} for r in rows]
        rules = AlertRule.objects.filter(user=request.user, enabled=True)[:5]
        context["alerts"] = [{
            "rule": r,
            "count": r.queryset().count(),
            "top": list(r.queryset().order_by("-total_risk_score")[:3]),
        } for r in rules]
    except Exception as exc:  # 数据库未就绪时页面不 500
        context.update({"enterprise_count": 0, "risk_count": 0, "high_count": 0,
                        "top_risks": [], "error": str(exc)})
    return render(request, "index.html", context)


def health(request):
    """健康检查：返回数据库版本与表数量，供答辩演示与自检。"""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute("SELECT VERSION()")
        version = cur.fetchone()[0]
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
    return JsonResponse({"ok": True, "mysql": version, "tables": tables},
                        json_dumps_params={"ensure_ascii": False})


def _status_counts():
    rows = Enterprise.objects.values("ope_status").annotate(n=Count("id")).order_by("-n")
    return [(STATUS.get(r["ope_status"], r["ope_status"] or "未知"), r["n"]) for r in rows]


def _year_counts():
    """按 5 年一个区间聚合，避免年份太密导致图挤在一起。"""
    rows = (Enterprise.objects.exclude(est_date__isnull=True)
            .values("est_date__year").annotate(n=Count("id")))
    buckets = {}
    for r in rows:
        y = r["est_date__year"]
        if not y:
            continue
        start = 1990 if y < 1990 else (y // 5) * 5
        key = "1990 年前" if y < 1990 else f"{start}–{start + 4}"
        buckets[key] = buckets.get(key, 0) + r["n"]
    return sorted(buckets.items())


def _capital_buckets():
    buckets = [("0–100 万", 0, 100), ("100–500 万", 100, 500),
               ("500–1000 万", 500, 1000), ("1000 万以上", 1000, 10 ** 9)]
    return [(label, Enterprise.objects.filter(reg_cap__gte=lo, reg_cap__lt=hi).count())
            for label, lo, hi in buckets]


def _city_counts():
    rows = (Enterprise.objects.exclude(city__isnull=True).exclude(city="")
            .values("city").annotate(n=Count("id")).order_by("-n")[:CITY_TOP])
    return [(r["city"], r["n"]) for r in rows]


def _level_counts():
    rows = RiskIndicator.objects.values("risk_level").annotate(n=Count("id")).order_by("-n")
    return [(LEVEL.get(r["risk_level"], r["risk_level"]), r["n"]) for r in rows]


def _score_hist():
    out = []
    for label, lo, hi in SCORE_BINS:
        out.append((label, RiskIndicator.objects.filter(total_risk_score__gte=lo,
                                                        total_risk_score__lt=hi).count()))
    return out


@login_required
def chart_enterprise(request):
    """企业数据可视化面板：状态、类别、城市分布。"""
    stats = {
        "enterprise_count": Enterprise.objects.count(),
        "status": _status_counts(),
        "years": _year_counts(),
        "capital": _capital_buckets(),
    }
    return render(request, "chart_enterprise.html", {"s": stats})


@login_required
def chart_risk(request):
    """风险数据可视化面板：等级、得分分布与 Top10。"""
    stats = {
        "risk_count": RiskIndicator.objects.count(),
        "avg_score": round(RiskIndicator.objects.aggregate(v=Avg("total_risk_score"))["v"] or 0, 2),
        "max_score": round(RiskIndicator.objects.aggregate(v=Max("total_risk_score"))["v"] or 0, 2),
        "high_count": RiskIndicator.objects.filter(risk_level="high").count(),
        "levels": _level_counts(),
        "hist": _score_hist(),
        "top": list(RiskIndicator.objects.order_by("-total_risk_score")[:10]
                    .values("name", "total_risk_score", "risk_level")),
    }
    return render(request, "chart_risk.html", {"s": stats})


@login_required
def chart_analysis(request):
    """分析看板：8 个统计视角 + 自动结论。"""
    return render(request, "chart_analysis.html", {"data": analytics.build()})


def chart_image(request, kind):
    """图片内容模块：把图表以 SVG 图片输出，可嵌入页面或直接下载。"""
    if kind == "status":
        svg = charts.pie_chart(_status_counts(), "企业经营状态分布")
    elif kind == "year":
        data = _year_counts()
        svg = charts.bar_chart([d[0] for d in data], [d[1] for d in data],
                               "企业成立年份分布", height=430, color=charts.TEAL)
    elif kind == "capital":
        data = _capital_buckets()
        svg = charts.hist_chart([d[0] for d in data], [d[1] for d in data],
                                "注册资本区间分布")
    elif kind == "level":
        svg = charts.pie_chart(_level_counts(), "风险等级分布")
    elif kind == "score":
        data = _score_hist()
        svg = charts.hist_chart([d[0] for d in data], [d[1] for d in data],
                                "企业风险得分分布")
    else:
        return HttpResponse("unknown chart", status=404)

    resp = HttpResponse(svg, content_type="image/svg+xml; charset=utf-8")
    if request.GET.get("download"):
        resp["Content-Disposition"] = f'attachment; filename="{kind}.svg"'
    return resp

@login_required
def enterprise_list(request):
    """企业列表：关键词、状态、资本区间、成立年份、登记机关、类型，支持下钻与导出。"""
    keyword = request.GET.get("keyword", "").strip()
    status = request.GET.get("status", "").strip()
    category = request.GET.get("category", "").strip()
    cap = request.GET.get("cap", "").strip()
    year = request.GET.get("year", "").strip()
    org = request.GET.get("org", "").strip()
    district = request.GET.get("district", "").strip()
    ftype = request.GET.get("type", "").strip()
    sort = request.GET.get("sort", "new")

    qs = Enterprise.objects.all()
    if keyword:
        qs = qs.filter(firm_name__icontains=keyword)
    if status:
        qs = qs.filter(ope_status=status)
    if category:
        qs = qs.filter(firm_category=category)
    cap_map = {
        "0-100": (0, 100), "100-500": (100, 500),
        "500-1000": (500, 1000), "1000+": (1000, 10 ** 12),
    }
    if cap in cap_map:
        lo, hi = cap_map[cap]
        qs = qs.filter(reg_cap__gte=lo, reg_cap__lt=hi)
    year_map = {
        "pre1990": (None, 1990), "1990-1994": (1990, 1995), "1995-1999": (1995, 2000),
        "2000-2004": (2000, 2005), "2005-2009": (2005, 2010), "2010-2014": (2010, 2015),
        "2015-2019": (2015, 2020), "2020+": (2020, 2100),
    }
    if year in year_map:
        lo, hi = year_map[year]
        if lo:
            qs = qs.filter(est_date__gte=f"{lo}-01-01")
        if hi:
            qs = qs.filter(est_date__lt=f"{hi}-01-01")
    if org:
        qs = qs.filter(reg_org=org)
    if district:
        qs = qs.filter(district=district)
    if ftype:
        qs = qs.filter(firm_type=ftype)

    order = {"new": "-id", "cap_desc": "-reg_cap", "old": "est_date"}.get(sort, "-id")
    qs = qs.order_by(order)

    if request.GET.get("export") == "csv":
        import csv

        from django.http import HttpResponse

        _ab_convert(request, "risk_export_cta")
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = ('attachment; filename="enterprise_list_' +
                                            __import__("datetime").date.today().strftime("%Y%m%d") + '.csv"')
        resp.write("﻿")
        writer = csv.writer(resp)
        writer.writerow(["企业名称", "统一社会信用代码", "法定代表人", "经营状态",
                         "注册资本(万元)", "成立日期", "登记机关", "企业类型"])
        for e in qs.iterator():
            writer.writerow([e.firm_name, e.usc_code, e.legal_rep,
                             e.get_ope_status_display(), e.reg_cap, e.est_date,
                             e.reg_org, e.firm_type])
        return resp

    ab_variant = _ab_impression(request, "ent_list_page_size")
    page_size = 20 if ab_variant == "B" else 10
    page_obj = Paginator(qs, page_size).get_page(request.GET.get("page"))
    chips = []
    if keyword:
        chips.append(("名称：" + keyword, "keyword"))
    if status:
        chips.append(("状态：" + dict([("1", "在营"), ("2", "注销"), ("3", "吊销")]).get(status, status), "status"))
    if cap:
        chips.append(("资本：" + cap + " 万", "cap"))
    if year:
        chips.append(("成立：" + year, "year"))
    if org:
        chips.append(("登记机关：" + org, "org"))
    if ftype:
        chips.append(("类型：" + ftype, "type"))
    if district:
        chips.append(("区县：" + _district_names().get(district, district), "district"))
    from urllib.parse import urlencode
    qs_suffix = urlencode({k: v for k, v in {
        "keyword": keyword, "status": status, "category": category,
        "cap": cap, "year": year, "org": org, "type": ftype,
        "district": district, "sort": sort,
    }.items() if v})
    return render(request, "enterprise_list.html", {
        "page_obj": page_obj,
        "keyword": keyword,
        "status": status,
        "category": category,
        "cap": cap,
        "year": year,
        "org": org,
        "type": ftype,
        "district": district,
        "sort": sort,
        "chips": chips,
        "ab_variant": ab_variant,
        "page_size": page_size,
        "qs_suffix": qs_suffix,
        "total": qs.count(),
        "status_choices": [("1", "在营"), ("2", "注销"), ("3", "吊销")],
        "cap_choices": ["0-100", "100-500", "500-1000", "1000+"],
        "year_choices": ["pre1990", "1990-1994", "1995-1999", "2000-2004",
                         "2005-2009", "2010-2014", "2015-2019", "2020+"],
    })


@login_required
def enterprise_detail(request, pk):
    """企业详情：基础信息 + 关联风险记录。"""
    enterprise = get_object_or_404(Enterprise, pk=pk)
    risks = enterprise.risk_indicators.order_by("-total_risk_score")
    if "/enterprise/list/" in (request.META.get("HTTP_REFERER") or ""):
        _ab_convert(request, "ent_list_page_size")
    return render(request, "enterprise_detail.html", {
        "enterprise": enterprise,
        "risks": risks,
        "latest_risk": risks.first(),
    })


@login_required
def risk_list(request):
    """风险列表：筛选、排序、四维/全指标切换、CSV 导出。"""
    keyword = request.GET.get("keyword", "").strip()
    code = request.GET.get("code", "").strip()
    level = request.GET.get("level", "").strip()
    score_min = request.GET.get("score_min", "").strip()
    score_max = request.GET.get("score_max", "").strip()
    sort = request.GET.get("sort", "score_desc")
    view = request.GET.get("view", "dims")

    qs = RiskIndicator.objects.select_related("enterprise").all()
    if keyword:
        qs = qs.filter(name__icontains=keyword)
    if code:
        qs = qs.filter(enterprise__usc_code__icontains=code)
    if level:
        qs = qs.filter(risk_level=level)
    try:
        if score_min:
            qs = qs.filter(total_risk_score__gte=float(score_min))
    except ValueError:
        score_min = ""
    try:
        if score_max:
            qs = qs.filter(total_risk_score__lte=float(score_max))
    except ValueError:
        score_max = ""
    order = {
        "score_desc": "-total_risk_score",
        "score_asc": "total_risk_score",
        "name": "name",
        "new": "-create_time",
    }.get(sort, "-total_risk_score")
    qs = qs.order_by(order)

    if request.GET.get("export") == "csv":
        import csv

        from django.http import HttpResponse

        _ab_convert(request, "risk_export_cta")
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = ('attachment; filename="risk_list_' +
                                            __import__("datetime").date.today().strftime("%Y%m%d") + '.csv"')
        resp.write("\ufeff")
        writer = csv.writer(resp)
        head = ["企业名称", "综合得分", "风险等级", "财务", "经营", "合规", "质量"]
        if view == "full":
            head += ["cai_1", "cai_2", "cai_3", "s_an_1", "s_an_2", "s_an_3",
                     "li_an_1", "li_an_2", "li_an_3", "zhi_1", "zhi_2", "zhi_3"]
        writer.writerow(head)
        # 性能优化 P-02：用 values_list 取元组，避免为 10000 行各建一个模型实例
        base_fields = ["name", "total_risk_score", "risk_level",
                       "financial_score", "operation_score",
                       "compliance_score", "quality_score"]
        extra_fields = ["cai_1", "cai_2", "cai_3", "s_an_1", "s_an_2", "s_an_3",
                        "li_an_1", "li_an_2", "li_an_3", "zhi_1", "zhi_2", "zhi_3"]
        fields = base_fields + (extra_fields if view == "full" else [])
        level_label = {"low": "低风险", "medium": "中风险", "high": "高风险"}
        for row in qs.values_list(*fields).iterator(chunk_size=2000):
            cells = list(row[:7])
            cells[2] = level_label.get(cells[2], cells[2])
            if view == "full":
                cells += list(row[7:])
            writer.writerow(cells)
        return resp

    ab_variant = _ab_impression(request, "risk_export_cta")
    page_obj = Paginator(qs, 10).get_page(request.GET.get("page"))
    from urllib.parse import urlencode
    qs_suffix = urlencode({k: v for k, v in {
        "keyword": keyword, "code": code, "level": level,
        "score_min": score_min, "score_max": score_max,
        "sort": sort, "view": view,
    }.items() if v})
    return render(request, "risk_list.html", {
        "ab_variant": ab_variant,
        "qs_suffix": qs_suffix,
        "page_obj": page_obj,
        "keyword": keyword,
        "code": code,
        "level": level,
        "score_min": score_min,
        "score_max": score_max,
        "sort": sort,
        "view": view,
        "total": qs.count(),
        "level_choices": [("high", "高风险"), ("medium", "中风险"), ("low", "低风险")],
    })


def _percentile(score):
    total = RiskIndicator.objects.count()
    if not total:
        return 0.0
    below = RiskIndicator.objects.filter(total_risk_score__lt=score).count()
    return round(below / total * 100, 1)


def _peer_avg(reg_cap):
    """同注册资本区间的平均分，作为“同规模对比”。"""
    cap = float(reg_cap or 0)
    lo, hi = 0, 10 ** 9
    if cap < 100:
        hi = 100
    elif cap < 500:
        lo, hi = 100, 500
    elif cap < 1000:
        lo, hi = 500, 1000
    else:
        lo = 1000
    qs = RiskIndicator.objects.filter(enterprise__reg_cap__gte=lo, enterprise__reg_cap__lt=hi)
    return round(float(qs.aggregate(v=Avg("total_risk_score"))["v"] or 0), 2)


@login_required
def risk_detail(request, pk):
    """风险详情：总分、四维、12 项指标、年度快照、同规模对比、AI 解读。"""
    risk = get_object_or_404(RiskIndicator.objects.select_related("enterprise"), pk=pk)
    snapshots = list(risk.enterprise.snapshots.all())
    peer = _peer_avg(risk.enterprise.reg_cap)
    import json
    items = []
    for dim, fields in [("财务", ("cai_1", "cai_2", "cai_3")),
                        ("经营", ("s_an_1", "s_an_2", "s_an_3")),
                        ("合规", ("li_an_1", "li_an_2", "li_an_3")),
                        ("质量", ("zhi_1", "zhi_2", "zhi_3"))]:
        for f in fields:
            v = float(getattr(risk, f))
            items.append({"dim": dim, "name": f, "value": round(v / 3, 2), "raw": v})
    breakdown = {
        "items": items,
        "dims": [
            {"name": "财务", "value": round(float(risk.financial_score) * 0.75, 2)},
            {"name": "经营", "value": round(float(risk.operation_score) * 0.75, 2)},
            {"name": "合规", "value": round(float(risk.compliance_score) * 0.75, 2)},
            {"name": "质量", "value": round(float(risk.quality_score) * 0.75, 2)},
        ],
        "total": float(risk.total_risk_score),
    }
    return render(request, "risk_detail.html", {
        "breakdown": breakdown,
        "risk": risk,
        "snapshots": snapshots,
        "has_demo": any("模拟" in (s.note or "") for s in snapshots),
        "percentile": _percentile(risk.total_risk_score),
        "peer_avg": peer,
        "diff": round(float(risk.total_risk_score) - peer, 2),
    })


@login_required
def chart_compare(request):
    """企业对比：页面内直接选 2–4 家（搜索添加 / 芯片移除），雷达 + 分组柱 + 表格。"""
    raw = request.GET.getlist("ids")
    ids = []
    for x in raw:
        for part in str(x).split(","):
            part = part.strip()
            if part.isdigit() and int(part) not in ids:
                ids.append(int(part))
    ids = ids[:4]

    keyword = request.GET.get("q", "").strip()
    ents = list(Enterprise.objects.filter(id__in=ids))
    risks = {r.enterprise_id: r for r in RiskIndicator.objects.filter(enterprise_id__in=ids)}

    import json

    rows, chart = [], []
    for e in ents:
        r = risks.get(e.id)
        if not r:
            continue
        peer = _peer_avg(e.reg_cap)
        rows.append({"ent": e, "risk": r,
                     "percentile": _percentile(r.total_risk_score),
                     "peer_avg": peer,
                     "diff": round(float(r.total_risk_score) - peer, 2)})
        chart.append({"name": e.firm_name, "total": float(r.total_risk_score),
                      "values": [float(r.financial_score), float(r.operation_score),
                                 float(r.compliance_score), float(r.quality_score)]})

    # ---- 候选企业：搜索优先，否则推荐高风险头部 ----
    picked = set(ids)
    if keyword:
        cand_qs = (Enterprise.objects.filter(firm_name__icontains=keyword)
                   .exclude(id__in=picked).order_by("-reg_cap")[:8])
        candidates = [{"ent": e, "score": None} for e in cand_qs]
    else:
        scored = (RiskIndicator.objects.select_related("enterprise")
                  .order_by("-total_risk_score")[:60])
        seen, candidates = set(), []
        for r in scored:
            if r.enterprise_id in picked or r.enterprise_id in seen:
                continue
            seen.add(r.enterprise_id)
            candidates.append({"ent": r.enterprise, "score": r.total_risk_score})
            if len(candidates) >= 8:
                break

    selected_ids = ",".join(str(i) for i in ids)
    # 每个已选企业一个“移除”链接
    selected = [{"ent": e,
                 "remove_ids": ",".join(str(i) for i in ids if i != e.id)}
                for e in ents]

    def add_url(new_id):
        return "?ids=" + (selected_ids + "," if selected_ids else "") + str(new_id)

    for c in candidates:
        c["add_url"] = add_url(c["ent"].id)

    scores = [float(x["risk"].total_risk_score) for x in rows]
    stats = {
        "count": len(rows),
        "max": round(max(scores), 2) if scores else 0,
        "min": round(min(scores), 2) if scores else 0,
        "avg": round(sum(scores) / len(scores), 2) if scores else 0,
    }
    return render(request, "chart_compare.html", {
        "rows": rows,
        "ids": ids,
        "selected_ids": selected_ids,
        "selected": selected,
        "candidates": candidates,
        "keyword": keyword,
        "stats": stats,
        "chart_json": json.dumps(chart, ensure_ascii=False),
    })


@login_required
@ensure_csrf_cookie
def ai_settings(request):
    """用户级 AI 配置：选择平台、填自己的 API Key。"""
    setting, _ = AISetting.objects.get_or_create(user=request.user)
    saved = False
    error = ""
    if request.method == "POST" and request.POST.get("action") == "clear_key":
        setting.api_key = ""
        setting.save()
        saved = True
    elif request.method == "POST":
        provider = request.POST.get("provider", "deepseek")
        base_url = request.POST.get("base_url", "").strip() or ai_service.DEFAULT_BASE.get(provider, "")
        model_name = request.POST.get("model_name", "").strip() or ai_service.DEFAULT_MODEL.get(provider, "")
        api_key = request.POST.get("api_key", "").strip()
        enabled = request.POST.get("enabled") == "on"

        setting.provider = provider
        setting.base_url = base_url
        setting.model_name = model_name
        setting.enabled = enabled
        if api_key:  # 留空表示不修改原 Key
            setting.api_key = api_key
        if not setting.api_key:
            error = "API Key 不能为空"
        else:
            setting.save()
            saved = True
    return render(request, "ai_settings.html", {
        "setting": setting,
        "saved": saved,
        "error": error,
        "providers": AISetting.PROVIDER_CHOICES,
    })


@login_required
def ai_test(request):
    """测试 Key：优先用表单里临时填的，其次用已保存的。"""
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "仅支持 POST"})
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}
    setting, _ = AISetting.objects.get_or_create(user=request.user)
    key = body.get("api_key") or setting.api_key
    base = body.get("base_url") or setting.base_url
    ok, message = ai_service.test_connection(base, key)
    if not ok:
        # 把底层 WinError 翻译成可操作提示：本机地址多半是本地服务没启动
        from urllib.parse import urlparse
        host = urlparse(base).hostname or ""
        refused = ("10061" in message) or ("积极拒绝" in message) or ("Connection refused" in message)
        if refused and host in ("127.0.0.1", "localhost"):
            message = (f"本机 {host} 上没有服务在监听（{message}）。"
                       f"如果你用的是本地 mock，请先启动它；"
                       f"否则把接口地址改成真实平台，例如 https://api.deepseek.com/v1")
        elif refused:
            message = f"目标 {host} 拒绝连接（{message}），检查地址与端口是否正确"
    return JsonResponse({"ok": ok, "message": message})


@login_required
def ai_analyze(request):
    """用当前用户自己的 Key 解读一条风险记录。"""
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "仅支持 POST"})
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}
    risk = RiskIndicator.objects.select_related("enterprise").filter(pk=body.get("risk_id")).first()
    if not risk:
        return JsonResponse({"ok": False, "message": "风险记录不存在"})
    setting = AISetting.objects.filter(user=request.user).first()
    if not setting or not setting.api_key:
        return JsonResponse({"ok": False, "need_key": True,
                             "message": "请先在「AI 平台配置」里填写你自己的 API Key"})
    text, err = ai_service.analyze_risk(setting.base_url, setting.api_key,
                                        setting.model_name, risk.enterprise, risk)
    if err:
        return JsonResponse({"ok": False, "message": err})
    AuditLog.objects.create(user=request.user, action="AI 解读", target=risk.name, ip=request.META.get("REMOTE_ADDR"))
    return JsonResponse({"ok": True, "text": text, "model": setting.model_name})


@admin_required
def manage_users(request):
    """管理员：查看所有账号与角色（普通用户看不到）。"""
    rows = []
    for u in User.objects.order_by("-is_superuser", "username"):
        profile = getattr(u, "profile", None)
        rows.append({
            "user": u,
            "role": "管理员" if u.is_superuser or (profile and profile.role == "admin") else "普通用户",
            "department": profile.department if profile else "",
            "last_login": u.last_login,
            "has_ai": bool(getattr(u, "ai_setting", None) and u.ai_setting.api_key),
        })
    return render(request, "manage_users.html", {"rows": rows, "total": len(rows)})


# ---------- 交互图表数据接口 ----------

def _quartiles(values):
    vals = sorted(values)
    if not vals:
        return [0, 0, 0, 0, 0]
    def q(p):
        idx = (len(vals) - 1) * p
        lo, hi = int(idx), min(int(idx) + 1, len(vals) - 1)
        return round(vals[lo] + (vals[hi] - vals[lo]) * (idx - lo), 2)
    return [round(vals[0], 2), q(0.25), q(0.5), q(0.75), round(vals[-1], 2)]


@login_required
def chart_data_enterprise(request):
    year = _year_counts()
    capital = _capital_buckets()
    orgs = list(Enterprise.objects.exclude(reg_org__isnull=True).exclude(reg_org="")
                .values("reg_org").annotate(n=Count("id")).order_by("-n")[:10])
    top_cap = list(Enterprise.objects.exclude(reg_cap__isnull=True)
                   .order_by("-reg_cap")[:10].values("firm_name", "reg_cap"))
    types = list(Enterprise.objects.values("firm_type").annotate(n=Count("id")).order_by("-n")[:8])
    return JsonResponse({
        "status": [{"name": n, "value": v} for n, v in _status_counts()],
        "capital": {"labels": [d[0] for d in capital], "values": [d[1] for d in capital]},
        "year": {"labels": [d[0] for d in year], "values": [d[1] for d in year]},
        "orgs": {"labels": [o["reg_org"] for o in orgs], "values": [o["n"] for o in orgs]},
        "top_cap": {"labels": [t["firm_name"] for t in top_cap],
                    "values": [float(t["reg_cap"] or 0) for t in top_cap]},
        "types": {"labels": [t["firm_type"] or "未知" for t in types],
                  "values": [t["n"] for t in types]},
        "total": Enterprise.objects.count(),
    }, json_dumps_params={"ensure_ascii": False})

@login_required
def chart_data_risk(request):
    levels = _level_counts()
    hist = _score_hist()
    top = list(RiskIndicator.objects.order_by("-total_risk_score")[:10]
               .values("name", "total_risk_score", "risk_level"))
    return JsonResponse({
        "levels": [{"name": n, "value": v} for n, v in levels],
        "hist": {"labels": [d[0] for d in hist], "values": [d[1] for d in hist]},
        "top": [{"name": t["name"], "score": float(t["total_risk_score"]),
                 "level": t["risk_level"]} for t in top],
        "dims": [
            {"name": "财务", "value": round(float(RiskIndicator.objects.aggregate(v=Avg("financial_score"))["v"] or 0), 2)},
            {"name": "经营", "value": round(float(RiskIndicator.objects.aggregate(v=Avg("operation_score"))["v"] or 0), 2)},
            {"name": "合规", "value": round(float(RiskIndicator.objects.aggregate(v=Avg("compliance_score"))["v"] or 0), 2)},
            {"name": "质量", "value": round(float(RiskIndicator.objects.aggregate(v=Avg("quality_score"))["v"] or 0), 2)},
        ],
        "avg": round(float(RiskIndicator.objects.aggregate(v=Avg("total_risk_score"))["v"] or 0), 2),
        "max": round(float(RiskIndicator.objects.aggregate(v=Max("total_risk_score"))["v"] or 0), 2),
        "count": RiskIndicator.objects.count(),
        "high": RiskIndicator.objects.filter(risk_level="high").count(),
    }, json_dumps_params={"ensure_ascii": False})

@login_required
def chart_data_analysis(request):
    """分析看板数据（与页面同源，便于前端单独取数/二次开发）。"""
    return JsonResponse(analytics.build(), json_dumps_params={"ensure_ascii": False})

def alerts(request):
    """预警订阅：新增、启停、删除规则，并显示当前命中数量。"""
    if request.method == "POST":
        action = request.POST.get("action", "add")
        if action == "add":
            name = request.POST.get("name", "").strip() or "未命名规则"
            metric = request.POST.get("metric", "total")
            level = request.POST.get("level", "")
            try:
                threshold = float(request.POST.get("threshold", "80"))
            except ValueError:
                threshold = 80.0
            threshold = max(0.0, min(100.0, threshold))
            AlertRule.objects.create(user=request.user, name=name, metric=metric,
                                     threshold=threshold, level=level)
        elif action in ("delete", "toggle"):
            rule = AlertRule.objects.filter(user=request.user,
                                            pk=request.POST.get("rule_id")).first()
            if rule:
                if action == "delete":
                    rule.delete()
                else:
                    rule.enabled = not rule.enabled
                    rule.save(update_fields=["enabled"])
        return redirect("risk_app:alerts")

    rules = AlertRule.objects.filter(user=request.user)
    rows = [{"rule": r, "count": r.queryset().count(),
             "top": list(r.queryset().order_by("-total_risk_score")[:5])} for r in rules]
    return render(request, "alerts.html", {
        "rows": rows,
        "metrics": AlertRule.METRIC_CHOICES,
        "levels": AlertRule.LEVEL_CHOICES,
    })


def _edge_path():
    import os
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    return next((p for p in candidates if os.path.exists(p)), None)


@login_required
def enterprise_report_pdf(request, pk):
    """导出企业风险评估报告 PDF，文件名 = 企业名称（含免责声明）。"""
    from datetime import datetime
    from io import BytesIO

    from .report_pdf import build_risk_pdf

    ent = get_object_or_404(Enterprise, pk=pk)
    risk = RiskIndicator.objects.filter(enterprise=ent).order_by("-id").first()
    if not risk:
        return HttpResponse("该企业暂无风险记录", status=404)
    calc = risk_calc.calc_risk({
        "cai_1": risk.cai_1, "cai_2": risk.cai_2, "cai_3": risk.cai_3,
        "s_an_1": risk.s_an_1, "s_an_2": risk.s_an_2, "s_an_3": risk.s_an_3,
        "li_an_1": risk.li_an_1, "li_an_2": risk.li_an_2, "li_an_3": risk.li_an_3,
        "zhi_1": risk.zhi_1, "zhi_2": risk.zhi_2, "zhi_3": risk.zhi_3,
    }, mode="points")
    pdf_bytes = build_risk_pdf(ent, risk, calc, datetime.now().strftime("%Y-%m-%d %H:%M"))
    filename = ent.firm_name + "-风险评估报告.pdf"
    return FileResponse(BytesIO(pdf_bytes), as_attachment=True, filename=filename,
                        content_type="application/pdf")


# ---------------------------------------------------------------------------
# A/B 测试页面
# ---------------------------------------------------------------------------
@admin_required
def ab_dashboard(request):
    """A/B 实验总览：假设、指标、样本、p 值、结论。"""
    experiments = ABExperiment.objects.all()
    rows = []
    for exp in experiments:
        real = exp.result(source="real")
        allr = exp.result()
        rows.append({"exp": exp, "real": real, "all": allr,
                     "has_sim": ABEvent.objects.filter(experiment=exp, source="sim").exists()})
    return render(request, "ab_dashboard.html", {"rows": rows})


@admin_required
def ab_detail(request, pk):
    """单个实验详情：分组流量、事件明细、统计量、样本量建议。"""
    exp = get_object_or_404(ABExperiment, pk=pk)
    real = exp.result(source="real")
    allr = exp.result()
    events = exp.events.select_related()[:50]
    assignments = exp.assignments.order_by("-create_time")[:20]
    return render(request, "ab_detail.html", {
        "exp": exp, "real": real, "all": allr,
        "events": events, "assignments": assignments,
        "need": allr["need"],
    })


@admin_required
def ab_toggle(request, pk):
    """启停实验 / 记录结论（仅管理员）。"""
    exp = get_object_or_404(ABExperiment, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "toggle":
            exp.status = "stopped" if exp.status == "running" else "running"
            exp.save(update_fields=["status"])
        elif action == "decision":
            exp.decision = request.POST.get("decision", "")[:20]
            exp.save(update_fields=["decision"])
        return redirect("risk_app:ab_detail", pk=exp.pk)
    return redirect("risk_app:ab_dashboard")


@login_required
def ab_event(request):
    """前端上报转化事件（POST，JSON）。"""
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "只接受 POST"}, status=405)
    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        payload = {}
    key = payload.get("key", "")
    exp = _ab_experiment(key)
    if not exp:
        return JsonResponse({"ok": False, "msg": "实验不存在或已停止"}, status=404)
    variant = exp.assign(_user_key(request))
    ABEvent.objects.create(experiment=exp, variant=variant,
                           user_key=_user_key(request), kind=payload.get("kind") or exp.metric)
    return JsonResponse({"ok": True, "variant": variant})


# ---------------------------------------------------------------------------
# AI 解读：图表 / 企业对比
# ---------------------------------------------------------------------------
def _facts_for(scope, payload, user):
    """按页面收集“事实”，只喂给模型真实统计，不让前端传字符串。"""
    import json as _json

    if scope == "compare":
        ids = [int(i) for i in str(payload.get("target", "")).split(",") if i.isdigit()][:4]
        ents = list(Enterprise.objects.filter(id__in=ids))
        risks = {r.enterprise_id: r for r in RiskIndicator.objects.filter(enterprise_id__in=ids)}
        lines, scores = [], []
        for e in ents:
            r = risks.get(e.id)
            if not r:
                continue
            scores.append(float(r.total_risk_score))
            lines.append(
                f"- {e.firm_name}：总分 {float(r.total_risk_score):.2f}，"
                f"财务 {float(r.financial_score):.0f}、经营 {float(r.operation_score):.0f}、"
                f"合规 {float(r.compliance_score):.0f}、质量 {float(r.quality_score):.0f}，"
                f"注册资本 {float(e.reg_cap or 0):.0f} 万，状态 {e.get_ope_status_display()}")
        if not lines:
            return None, None, "没有可对比的企业"
        head = (f"共 {len(lines)} 家企业；最高 {max(scores):.2f}、最低 {min(scores):.2f}、"
                f"平均 {sum(scores) / len(scores):.2f}；全库均值 35.17、高风险线 80。")
        return "企业风险指标对比", head + "\n" + "\n".join(lines), None

    if scope == "risk_detail":
        risk = RiskIndicator.objects.select_related("enterprise").filter(pk=payload.get("target")).first()
        if not risk:
            return None, None, "风险记录不存在"
        facts = (f"企业：{risk.enterprise.firm_name}\n总分 {float(risk.total_risk_score):.2f}"
                 f"（全库均值 35.17，80 为高风险线）\n"
                 f"四维：财务 {float(risk.financial_score):.0f}、经营 {float(risk.operation_score):.0f}、"
                 f"合规 {float(risk.compliance_score):.0f}、质量 {float(risk.quality_score):.0f}\n"
                 f"原始：cai {risk.cai_1}/{risk.cai_2}/{risk.cai_3}，"
                 f"s_an {risk.s_an_1}/{risk.s_an_2}/{risk.s_an_3}，"
                 f"li_an {risk.li_an_1}/{risk.li_an_2}/{risk.li_an_3}，"
                 f"zhi {risk.zhi_1}/{risk.zhi_2}/{risk.zhi_3}")
        return f"风险详情 · {risk.enterprise.firm_name}", facts, None

    # 图表类：一律用服务端聚合，忽略前端的 title，避免越权取数
    if scope == "chart_enterprise":
        status = _status_counts()
        cap = _capital_buckets()
        year = _year_counts()
        total = Enterprise.objects.count()
        facts = (f"企业总数 {total}；经营状态：" + "、".join(f"{k} {v}" for k, v in status) +
                 "；资本区间：" + "、".join(f"{k} {v}" for k, v in cap) +
                 "；成立年份：" + "、".join(f"{k} {v}" for k, v in year[:5]))
        return "企业基本信息可视化", facts, None

    if scope == "chart_risk":
        total = RiskIndicator.objects.count()
        levels = dict((x["risk_level"], x["n"]) for x in
                      RiskIndicator.objects.values("risk_level").annotate(n=Count("id")))
        hist = _score_hist()
        avg = RiskIndicator.objects.aggregate(v=Avg("total_risk_score"))["v"] or 0
        facts = (f"记录 {total} 条；低 {levels.get('low', 0)}、中 {levels.get('medium', 0)}、"
                 f"高 {levels.get('high', 0)}；平均 {float(avg):.2f}；"
                 f"分档：" + "、".join(f"{k} {v}" for k, v in hist))
        return "企业风险信息可视化", facts, None

    if scope == "chart_analysis":
        d = analytics.build()
        target = str(payload.get("target", ""))
        n = max(d["n"], 1)
        share = d["counts"]["high"] / n * 100
        if target == "lorentz":
            facts = (f"样本 {d['n']}；基尼系数 {d['gini']}；前 10% 企业贡献 {d['lorentz']['top10']}% 的风险分")
        elif target == "band":
            b = d["bands"][0]
            facts = (f"按注册资本分组看分位：{b['bucket']} 组 n={b['n']}，"
                     f"P25={b['p25']}、P50={b['p50']}、P90={b['p90']}；超过本组 P90 即同规模偏高")
        elif target == "corr":
            off = [c for c in d["corr"]["r"] if c[0] != c[1]]
            best = max(off, key=lambda c: abs(c[2])) if off else [0, 0, 0]
            facts = f"四维两两相关最强 r={best[2]}；相关高说明四维在说同一件事，加权会重复计风险"
        elif target == "resid":
            facts = (f"状态×等级 卡方 χ²={d['residual']['chi2']}，df={d['residual']['dof']}，"
                     f"p={d['chi2_p']}；p>0.05 说明经营状态与风险等级没有显著关联")
        elif target == "radar":
            facts = "三组雷达：全库均值、高风险组、低风险组；高风险组四维整体外扩，说明风险是全面的"
        elif target == "quadrant":
            facts = "资本×得分象限：小资本 + 高分＝重点关注；大资本 + 低分＝相对稳健"
        elif target == "outlier":
            top = d["outliers"][0]["name"] if d["outliers"] else "—"
            facts = f"同规模异常 {len(d['outliers'])} 家（z≥2），最高为 {top}"
        elif target == "hist":
            facts = (f"样本 {d['n']}；高风险 {d['counts']['high']} 家（{share:.2f}%）、"
                     f"中 {d['counts']['medium']}、低 {d['counts']['low']}")
        else:
            facts = (f"样本 {d['n']}；高风险 {d['counts']['high']} 家（{share:.2f}%）；基尼 {d['gini']}")
        return "风险分析看板", facts, None

    if scope == "chart_map":
        rows = _map_rows()
        top3 = "、".join(f"{r['name']} {r['count']} 家" for r in rows[:3])
        worst = max(rows, key=lambda r: r["high_rate"]) if rows else None
        facts = (f"覆盖 {len(rows)} 个区县、{sum(r['count'] for r in rows)} 家企业；"
                 f"企业最多：{top3}；"
                 + (f"高风险占比最高：{worst['name']} {worst['high_rate']}%；" if worst else "")
                 + f"全市高风险 {sum(r['high'] for r in rows)} 家")
        return "重庆企业分布", facts, None

    return None, None, "未知页面"


@login_required
def ai_explain(request):
    """图表/对比页的 AI 解读：用户自己的 Key，结果落库供管理员查看。"""
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "仅支持 POST"})
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}
    scope = body.get("scope", "")
    setting = AISetting.objects.filter(user=request.user).first()
    if not setting or not setting.api_key:
        return JsonResponse({"ok": False, "need_key": True,
                             "message": "请先在「AI 平台配置」里填写你自己的 API Key"})

    title, facts, err = _facts_for(scope, body, request.user)
    if err:
        return JsonResponse({"ok": False, "message": err})

    text, err = ai_service.explain(setting.base_url, setting.api_key,
                                   setting.model_name, title, facts)
    AIInsight.objects.create(
        user=request.user, scope=scope, target=str(body.get("target", ""))[:120],
        title=title, facts=facts, answer=text or "",
        model_name=setting.model_name, ok=not err, error=(err or "")[:200])
    if err:
        return JsonResponse({"ok": False, "message": err})
    AuditLog.objects.create(user=request.user, action="AI 图表解读", target=title,
                            ip=request.META.get("REMOTE_ADDR"))
    return JsonResponse({"ok": True, "text": text, "model": setting.model_name, "facts": facts})


@admin_required
def ai_insights(request):
    """管理员：集中查看所有人（含普通用户）的 AI 解读记录。"""
    scope = request.GET.get("scope", "")
    qs = AIInsight.objects.select_related("user")
    if scope:
        qs = qs.filter(scope=scope)
    total = qs.count()
    rows = list(qs[:100])
    return render(request, "ai_insights.html", {
        "rows": rows, "total": total, "scope": scope,
        "scopes": AIInsight.SCOPE_CHOICES,
        "ok_count": qs.filter(ok=True).count(),
        "fail_count": qs.filter(ok=False).count(),
    })


# ---------------------------------------------------------------------------
# 重庆区县地图
# ---------------------------------------------------------------------------
_GEO_NAMES = None


def _district_names():
    """adcode → 区县名（来自本地 GeoJSON，只读一次）。"""
    global _GEO_NAMES
    if _GEO_NAMES is None:
        import os

        from django.conf import settings
        path = os.path.join(settings.BASE_DIR, "risk_app", "static", "json", "chongqing.json")
        with open(path, encoding="utf-8") as fh:
            geo = json.load(fh)
        _GEO_NAMES = {str(f["properties"]["adcode"]): f["properties"]["name"]
                      for f in geo["features"]}
    return _GEO_NAMES


def _map_rows():
    """按区县聚合：企业数、高风险数、平均分、高风险占比。

    性能优化 P-04：原实现把 1 万行整表取回 Python 逐行累加；
    改为 SQL GROUP BY（38 个区县）后再做名称映射，Python 侧从 1 万次循环降到 38 次。
    """
    names = _district_names()
    agg = (RiskIndicator.objects
           .values("enterprise__district")
           .annotate(count=Count("id"),
                     high=Count("id", filter=Q(risk_level="high")),
                     avg_score=Avg("total_risk_score"))
           .order_by("-count"))
    out = []
    for r in agg:
        code = str(r["enterprise__district"] or "")
        if code not in names:
            continue
        count = r["count"] or 0
        out.append({
            "code": code,
            "name": names[code],
            "count": count,
            "high": r["high"] or 0,
            "avg_score": round(float(r["avg_score"] or 0), 2),
            "high_rate": round((r["high"] or 0) / count * 100, 2) if count else 0,
        })
    out.sort(key=lambda x: -x["count"])
    return out


@login_required
def chart_map(request):
    """重庆企业分布地图页。"""
    rows = _map_rows()
    in_cq = Enterprise.objects.filter(province="500000").count()
    return render(request, "chart_map.html", {
        "rows": rows,
        "total": sum(r["count"] for r in rows),
        "high": sum(r["high"] for r in rows),
        "in_cq": in_cq,
        "outside": max(Enterprise.objects.count() - in_cq, 0),
        "top": rows[:5],
        "districts": len(rows),
        "geo_total": len(_district_names()),
        "all_total": Enterprise.objects.count(),
    })


@login_required
def chart_data_map(request):
    rows = _map_rows()
    return JsonResponse({"rows": rows, "total": sum(r["count"] for r in rows)},
                        json_dumps_params={"ensure_ascii": False})


# ---------------------------------------------------------------------------
# 自建管理后台
# ---------------------------------------------------------------------------
@admin_required
def console(request):
    """自建后台首页：概览 + 入口 + 审计日志。仅管理员。"""
    from django.db import connection

    total_ent = Enterprise.objects.count()
    total_risk = RiskIndicator.objects.count()
    high = RiskIndicator.objects.filter(risk_level="high").count()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            db_status = "已连接（MySQL）"
    except Exception as exc:  # pragma: no cover
        db_status = "异常：" + str(exc)[:40]

    profile = getattr(request.user, "profile", None)
    role_label = "管理员" if is_admin(request.user) else "普通用户"
    if profile and profile.role == "admin" and not request.user.is_superuser:
        role_label = "管理员（业务角色）"

    logs = AuditLog.objects.select_related("user").order_by("-id")[:10]
    return render(request, "console.html", {
        "role_label": role_label,
        "logs": logs,
        "kpi": {
            "enterprises": total_ent,
            "risks": total_risk,
            "high": high,
            "high_rate": round(high / total_risk * 100, 2) if total_risk else 0,
            "users": User.objects.count(),
            "admins": User.objects.filter(is_superuser=True).count(),
            "insights": AIInsight.objects.count(),
            "ai_ready": AISetting.objects.exclude(api_key="").count(),
            "alerts": AlertRule.objects.count(),
            "experiments": ABExperiment.objects.count(),
            "db_status": db_status,
            "last_audit": logs[0].create_time.strftime("%m-%d %H:%M") if logs else "—",
        },
    })


# ---------------------------------------------------------------------------
# 项目 14：企业风险预估（调用大模型平台）
# ---------------------------------------------------------------------------
INDUSTRY_CHOICES = ["互联网和软件", "制造业", "批发零售", "建筑", "教育",
                    "房地产", "金融", "物流", "其他"]
SCALE_CHOICES = [("large", "大型企业"), ("medium", "中型企业"),
                 ("small", "小型企业"), ("micro", "微型企业")]


@login_required
def predict_page(request):
    """AI 风险预估页面：表单 + 四态结果区。"""
    setting = AISetting.objects.filter(user=request.user).first()
    return render(request, "predict.html", {
        "industries": INDUSTRY_CHOICES,
        "scales": SCALE_CHOICES,
        "has_key": bool(setting and setting.api_key),
        "model_name": setting.model_name if setting else llm_predict.API_CONFIG["model"],
        "base_url": setting.base_url if setting else llm_predict.API_CONFIG["base_url"],
        "dimensions": llm_predict.DIMENSIONS,
    })


@login_required
def predict_api(request):
    """AI 风险预估接口：校验参数 → 调用封装 → 统一返回结构。"""
    if request.method != "POST":
        return JsonResponse({"code": -1, "message": "仅支持 POST 请求"})

    enterprise_name = (request.POST.get("enterprise_name") or "").strip()
    if not enterprise_name:
        return JsonResponse({"code": -1, "message": "企业名称不能为空"})
    if len(enterprise_name) > 80:
        return JsonResponse({"code": -1, "message": "企业名称过长（不超过 80 字）"})

    description = request.POST.get("description") or ""
    if len(description) > 20000:
        return JsonResponse({"code": -1, "message": "描述过长（不超过 20000 字）"})
    if len(description) > llm_predict.API_CONFIG["max_desc_chars"]:
        # 超长文本不报错，截断后分析并在 meta 里标记
        pass

    setting = AISetting.objects.filter(user=request.user).first()
    try:
        result, meta = llm_predict.llm_risk_analysis(
            enterprise_name=enterprise_name,
            credit_code=request.POST.get("credit_code", ""),
            description=description,
            industry=request.POST.get("industry", ""),
            scale=request.POST.get("scale", "small"),
            setting=setting,
        )
    except Exception as exc:  # 兜底：任何未预期异常都不把堆栈抛给前端
        return JsonResponse({"code": -1, "message": "分析失败：%s" % exc})

    AuditLog.objects.create(user=request.user, action="AI 风险预估",
                            target=enterprise_name, ip=request.META.get("REMOTE_ADDR"))
    return JsonResponse({"code": 0, "data": result, "meta": meta,
                         "input": {"enterprise_name": enterprise_name,
                                   "credit_code": request.POST.get("credit_code", ""),
                                   "industry": request.POST.get("industry", ""),
                                   "scale": request.POST.get("scale", "small")}})


# ---------------------------------------------------------------------------
# 项目 15：本地 NLP 微服务（Docker）的前端展示
# ---------------------------------------------------------------------------
NLP_DEMO_TEXT = (
    "该公司近两年连续亏损，利润下滑，资金链断裂，存在债务违约与财务造假嫌疑，已资不抵债，"
    "坏账与欠款持续增加；主营业务停产，大规模裁员，市场份额萎缩，供应链中断，高管离职。"
    "因违规被证监会立案调查，受到行政处罚并罚款，涉及多起诉讼，被列为失信被执行人，涉嫌违法；"
    "此外安全事故被媒体曝光，引发消费者投诉与维权举报，形成负面新闻。"
)


@login_required
@ensure_csrf_cookie
def model_show(request):
    """本地模型识别页：左侧输入、右侧结果；顶部显示微服务在线状态。"""
    ok, health = nlp_infer.service_health()
    return render(request, "model_show.html", {
        "demo_text": NLP_DEMO_TEXT,
        "service_ok": ok,
        "service_info": health,
        "service_url": nlp_infer.NLP_SERVICE_URL,
    })


@login_required
def model_analyze(request):
    """前端提交文本 → 调用本地 NLP 服务 → 返回 {code, message, data}。

    code=0 成功；code=1 失败或降级（服务未启动时 message 会提示怎么启动），
    页面据此提示而不是报 500。
    """
    if request.method != "POST":
        return JsonResponse({"code": 1, "message": "仅支持 POST"})
    text = request.POST.get("text", "")
    if not text:
        try:
            text = (json.loads(request.body.decode("utf-8") or "{}") or {}).get("text", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            text = ""

    data = nlp_infer.nlp_text_analysis(text)
    if data["ok"]:
        AuditLog.objects.create(user=request.user, action="本地模型识别",
                                target=(text[:40] + ("…" if len(text) > 40 else "")),
                                ip=request.META.get("REMOTE_ADDR"))
    return JsonResponse(
        {"code": 0 if data["ok"] else 1, "message": data["message"], "data": data},
        json_dumps_params={"ensure_ascii": False},
    )
