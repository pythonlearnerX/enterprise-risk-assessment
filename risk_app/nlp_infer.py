# -*- coding: utf-8 -*-
"""Django 侧对 NLP 微服务的调用封装（项目 15）。

三条原则
--------
1. 超时：网络调用一律 timeout=5，避免请求线程被拖住；
2. 降级：服务没启动、返回异常、格式不对，都返回带 message 的空结果，
   页面提示“先启动 NLP 服务”，而不是抛 500；
3. 转换：把服务返回的 details 结构转成页面直接可用的扁平结构，
   并在后端完成 HTML 转义 + 关键词高亮（前端只负责展示）。
"""
import json
import os
from html import escape
from urllib import error, request

NLP_SERVICE_URL = os.environ.get("NLP_SERVICE_URL", "http://127.0.0.1:5000")
TIMEOUT = 5

CATEGORY_KEYS = {
    "财务": "financial",
    "经营": "operation",
    "合规": "compliance",
    "舆情": "public_opinion",
}

LEVEL_LABELS = {"high": "高风险", "medium": "中风险", "low": "低风险"}


def call_nlp_service(text):
    """调用 /analyze，失败返回 None（不抛异常）。"""
    try:
        payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            NLP_SERVICE_URL + "/analyze", data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
        )
        with request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (error.URLError, OSError, ValueError):
        return None


def _empty_result(message):
    return {
        "ok": False,
        "message": message,
        "total_score": 0,
        "risk_level": "",
        "level_label": "",
        "finance_score": 0,
        "operation_score": 0,
        "compliance_score": 0,
        "public_opinion_score": 0,
        "keywords": {"财务": [], "经营": [], "合规": [], "舆情": []},
        "highlighted_text": "",
        "summary": message,
    }


def _highlight(text, details):
    """先整体转义，再把命中词包 <b>，防止输入里的 HTML 被执行。

    注意不能「逐个 replace」：先替换「行政处罚」再替换「处罚」会把标签套进标签里，
    产生 <b>行政<b>处罚</b></b>。这里改为在原文上定位区间，长词优先、不重叠，再拼接。
    """
    hits = set()
    for key in CATEGORY_KEYS.values():
        hits.update(details.get(key, {}).get("keywords", []))
    hits = {h for h in hits if h}
    if not hits:
        return escape(text).replace("\n", "<br>")

    spans = []
    for kw in sorted(hits, key=len, reverse=True):
        start = 0
        while True:
            i = text.find(kw, start)
            if i < 0:
                break
            spans.append((i, i + len(kw)))
            start = i + len(kw)

    spans.sort()
    merged, last_end = [], -1
    for s0, e0 in spans:
        if s0 < last_end:          # 与已选区间重叠（短词落在长词里），丢弃
            continue
        merged.append((s0, e0))
        last_end = e0

    out, cursor = [], 0
    for s0, e0 in merged:
        out.append(escape(text[cursor:s0]))
        out.append('<b class="nlp-hit">%s</b>' % escape(text[s0:e0]))
        cursor = e0
    out.append(escape(text[cursor:]))
    return "".join(out).replace("\n", "<br>")


def nlp_text_analysis(text):
    """主入口：返回页面直接可用的结构；服务不可用时降级。"""
    if not text or not text.strip():
        return _empty_result("文本为空，请先输入要分析的文本")

    result = call_nlp_service(text)
    if not result or "details" not in result:
        return _empty_result(
            "NLP 服务未启动：请先运行 docker run -d -p 5000:5000 --name nlp-risk nlp-risk"
        )
    if result.get("error"):
        return _empty_result(result["error"])

    d = result["details"]
    keywords = {}
    for cn, key in CATEGORY_KEYS.items():
        keywords[cn] = d.get(key, {}).get("keywords", [])

    level = result.get("risk_level", "")
    return {
        "ok": True,
        "message": "",
        "total_score": result.get("total_score", 0),
        "risk_level": level,
        "level_label": LEVEL_LABELS.get(level, "未知"),
        "finance_score": d.get("financial", {}).get("score", 0),
        "operation_score": d.get("operation", {}).get("score", 0),
        "compliance_score": d.get("compliance", {}).get("score", 0),
        "public_opinion_score": d.get("public_opinion", {}).get("score", 0),
        "keywords": keywords,
        "highlighted_text": _highlight(text, d),
        "summary": "命中 %s 个风险词，综合 %s 分（%s）" % (
            result.get("keywords_found", 0),
            result.get("total_score", 0),
            LEVEL_LABELS.get(level, "未知"),
        ),
    }


def service_health():
    """探活：供页面显示“服务在线/离线”徽标。"""
    try:
        with request.urlopen(NLP_SERVICE_URL + "/health", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("status") == "ok", data
    except (error.URLError, OSError, ValueError):
        return False, {"status": "down", "service": "nlp-risk-analyzer"}