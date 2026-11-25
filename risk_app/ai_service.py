# -*- coding: utf-8 -*-
"""极简 AI 客户端：只用标准库 urllib，兼容 OpenAI 风格的 /chat/completions。"""
import json
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "custom": "",
}
DEFAULT_MODEL = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "custom": "",
}


def _call(url, key, payload=None, method="GET", timeout=30):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + key)
    req.add_header("Content-Type", "application/json")
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        # 本机地址绕过系统代理，避免 mock/内网服务被代理拦掉
        if host in ("127.0.0.1", "localhost"):
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            resp = opener.open(req, timeout=timeout)
        else:
            resp = urllib.request.urlopen(req, timeout=timeout)
        with resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        return None, f"HTTP {exc.code}：{body}"
    except urllib.error.URLError as exc:
        return None, f"网络不可达：{exc.reason}"
    except Exception as exc:  # 超时、解析失败等
        return None, f"调用失败：{exc}"


def test_connection(base_url, api_key):
    """GET /models 验证 Key 是否可用。"""
    if not api_key:
        return False, "请先填写 API Key"
    url = base_url.rstrip("/") + "/models"
    data, err = _call(url, api_key, timeout=15)
    if err:
        return False, err
    models = [m.get("id", "") for m in (data or {}).get("data", [])][:3]
    return True, "连接成功" + ("，可用模型：" + "、".join(models) if models else "")


def analyze_risk(base_url, api_key, model, enterprise, risk):
    """让模型给一条风险记录做简要解读。"""
    if not api_key:
        return None, "请先配置 API Key"
    prompt = (
        "你是一名企业风险评估顾问。请用 120 字以内、分三点解读下面这条风险记录，"
        "指出主要风险、可能原因和一条可执行建议。不要编造数据。\n"
        f"企业：{enterprise.firm_name}\n"
        f"综合得分：{risk.total_risk_score}（百分制，越高越差）\n"
        f"风险等级：{risk.get_risk_level_display()}\n"
        f"四维得分：财务 {risk.financial_score}、经营 {risk.operation_score}、"
        f"合规 {risk.compliance_score}、质量 {risk.quality_score}\n"
        f"原始指标：cai={risk.cai_1}/{risk.cai_2}/{risk.cai_3}，"
        f"s_an={risk.s_an_1}/{risk.s_an_2}/{risk.s_an_3}，"
        f"li_an={risk.li_an_1}/{risk.li_an_2}/{risk.li_an_3}，"
        f"zhi={risk.zhi_1}/{risk.zhi_2}/{risk.zhi_3}"
    )
    payload = {
        "model": model or "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 400,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    data, err = _call(url, api_key, payload, method="POST", timeout=60)
    if err:
        return None, err
    try:
        return data["choices"][0]["message"]["content"].strip(), None
    except (KeyError, IndexError, TypeError):
        return None, "返回格式不符合 OpenAI 规范"

def explain(base_url, api_key, model, title, facts, style="图表解读"):
    """通用解读：给定标题与事实清单，让模型输出三点结论。"""
    if not api_key:
        return None, "请先配置 API Key"
    prompt = (
        f"你是一名数据分析师。下面是「{title}」的{style}所需事实（来自系统真实统计）。\n"
        f"{facts}\n\n"
        "请严格基于上述数字，输出三点，每点一行、不超过 40 字：\n"
        "1) 最值得注意的现象；2) 可能的原因或业务含义；3) 一条可执行的建议。\n"
        "不要编造未给出的数据，不要复述原始数字清单。"
    )
    payload = {
        "model": model or "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 420,
    }
    url = base_url.rstrip("/") + "/chat/completions"
    data, err = _call(url, api_key, payload, method="POST", timeout=60)
    if err:
        return None, err
    try:
        return data["choices"][0]["message"]["content"].strip(), None
    except (KeyError, IndexError, TypeError):
        return None, "返回格式不符合 OpenAI 规范"
