# -*- coding: utf-8 -*-
"""项目 14：企业风险预估（调用大模型平台）

职责（对应实训指导书表 14-3 / 表 14-6）：
    1. 提示词：SYSTEM 约束角色、维度、权重、等级阈值与 JSON 格式；USER 装配企业信息。
    2. 调用封装：构造请求、超时与重试、401/429 分类处理。
    3. 解析：三级容错（直接解析 → 代码块 → 花括号截取 → 默认结构）。
    4. 校验：分数区间、维度数量与名称、等级与分数一致性，异常值就地修正。
    5. 降级：无 Key、网络异常、解析失败时返回本地模拟结果，页面不崩。

密钥来源优先级：调用方传入的 AISetting（每账号自己的 Key） > 环境变量 LLM_API_KEY。
密钥不落代码，符合指导书“密钥不得硬编码”的要求。
"""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# 一、配置（可用环境变量覆盖，便于切换模型平台）
# ---------------------------------------------------------------------------
API_CONFIG = {
    "base_url": os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1"),
    "api_key": os.environ.get("LLM_API_KEY", ""),
    "model": os.environ.get("LLM_MODEL", "deepseek-chat"),
    "timeout": int(os.environ.get("LLM_TIMEOUT", "30")),
    "max_retries": int(os.environ.get("LLM_MAX_RETRIES", "2")),
    "temperature": 0.3,
    "max_desc_chars": 1200,          # 超长描述截断，控制 token 与提示注入面
    "summary_limit": 100,            # 摘要 100 字以内
}

# 四维度固定顺序、权重与展示色（前端进度条/雷达图取色）
DIMENSIONS = [
    {"name": "财务风险", "weight": 0.40, "color": "#5eead4"},
    {"name": "经营风险", "weight": 0.25, "color": "#60a5fa"},
    {"name": "合规风险", "weight": 0.35, "color": "#fb7185"},
    {"name": "舆情风险", "weight": 0.00, "color": "#fbbf24"},
]
DIMENSION_NAMES = [d["name"] for d in DIMENSIONS]
WEIGHTS = {d["name"]: d["weight"] for d in DIMENSIONS}

LEVEL_TEXT = {"low": "低风险", "medium": "中风险", "high": "高风险"}
LEVEL_COLOR = {"low": "#34d399", "medium": "#fbbf24", "high": "#fb7185"}

# ---------------------------------------------------------------------------
# 二、系统提示词（角色 / 维度 / 评分规则 / 等级阈值 / 输出格式 / 约束）
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
你是一名专业的企业风险评估分析师，擅长从多个维度对企业进行风险评估。
你的任务是根据提供的企业信息，进行全面的风险分析，并输出结构化的JSON结果。

分析维度：
1. 财务风险：评估企业的财务健康状况、偿债能力、盈利能力、现金流等
2. 经营风险：评估企业的经营稳定性、市场竞争力、供应链、管理团队等
3. 合规风险：评估企业的合规性、法律风险、监管风险、行政处罚等
4. 舆情风险：评估企业的公众形象、负面舆情、品牌声誉等

评分规则：
- 每个维度0-100分，分数越高表示风险越大
- 综合得分 = 财务*40% + 经营*25% + 合规*35%
- 风险等级：低风险(0-40分)、中风险(40-70分)、高风险(70-100分)

输出格式要求（严格JSON格式，不要其他文字）：
{
    "total_score": 综合得分数字,
    "risk_level": "low/medium/high",
    "summary": "风险评估摘要，100字以内",
    "dimensions": [
        {"name": "财务风险", "score": 分数, "color": "#颜色", "description": "分析说明"},
        ...共4个维度
    ],
    "suggestions": ["建议1", "建议2", "建议3", "建议4"]
}

请确保输出是合法的JSON格式，可以直接被json.loads解析。
""".strip()


# ---------------------------------------------------------------------------
# 三、用户提示词装配
# ---------------------------------------------------------------------------
def build_user_prompt(enterprise_name, credit_code="", description="",
                      industry="", scale="small"):
    """把表单数据装配成自然语言；缺失信息给出默认表述，避免模型拒答。"""
    scale_text = {"large": "大型企业", "medium": "中型企业",
                  "small": "小型企业", "micro": "微型企业"}.get(scale, "小型企业")
    desc = (description or "").strip()
    truncated = False
    if len(desc) > API_CONFIG["max_desc_chars"]:
        desc = desc[:API_CONFIG["max_desc_chars"]]
        truncated = True
    if not desc:
        desc = "未提供详细描述，请基于行业和规模进行一般性风险评估。"
    elif truncated:
        desc += "（描述过长已截断，仅依据以上内容分析）"

    credit_line = "统一社会信用代码：%s\n" % credit_code.strip() if credit_code.strip() else ""
    prompt = """
请对以下企业进行风险评估：

企业名称：%s
%s所属行业：%s
企业规模：%s

企业信息描述：
%s

请按照系统提示的要求，进行全面的风险分析，并输出JSON格式的结果。
""" % (enterprise_name.strip(), credit_line, industry.strip() or "未提供", scale_text, desc)
    return prompt.strip(), truncated


# ---------------------------------------------------------------------------
# 四、三级容错解析
# ---------------------------------------------------------------------------
def _default_result(summary="AI分析结果解析失败，已使用默认结构", total=50):
    return {
        "total_score": total,
        "risk_level": "medium",
        "summary": summary,
        "dimensions": [
            {"name": d["name"], "score": total, "color": d["color"],
             "description": "解析失败，返回默认值"}
            for d in DIMENSIONS
        ],
        "suggestions": ["请重试一次分析", "建议人工复核企业公开信息",
                        "关注司法涉诉与行政处罚记录", "定期跟踪企业舆情变化"],
    }


def parse_llm_response(text):
    """三级容错：直接解析 → ```json 代码块 → 花括号截取 → 默认结构。"""
    if isinstance(text, dict):
        return text
    raw = (text or "").strip()
    if not raw:
        return _default_result()
    # 1) 直接解析
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 2) Markdown 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 3) 花括号截取（模型前后夹带解释文字）
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # 4) 兜底
    return _default_result()


# ---------------------------------------------------------------------------
# 五、结构校验（表 14-7）
# ---------------------------------------------------------------------------
def _clamp_score(value, default=50):
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    if num != num:  # NaN
        return default
    return int(round(max(0.0, min(100.0, num))))


def level_of(score):
    """按分数判定等级：0-40 低、40-70 中、70-100 高（40 与 70 边界归入上一档）。"""
    if score < 40:
        return "low"
    if score < 70:
        return "medium"
    return "high"


def validate_result(data):
    """校验并修正模型输出，返回 (规范后的结果, 问题清单)。"""
    issues = []
    if not isinstance(data, dict):
        data = {}
        issues.append("返回结构不是对象，已使用默认结构")

    # 维度：按固定四维度归并，缺失补齐，越界截断
    raw_dims = data.get("dimensions") or []
    by_name = {}
    for item in raw_dims:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        for std in DIMENSION_NAMES:
            if std in name or name in std:
                by_name[std] = item
                break
    dims = []
    for spec in DIMENSIONS:
        name = spec["name"]
        item = by_name.get(name)
        if item is None:
            issues.append("缺少维度：%s，已补默认值" % name)
            dims.append({"name": name, "score": 50, "color": spec["color"],
                         "description": "模型未返回该维度，按中性风险处理"})
            continue
        score = _clamp_score(item.get("score"))
        if score != item.get("score"):
            issues.append("维度 %s 分数越界或非法，已截断到 %s" % (name, score))
        desc = str(item.get("description") or "").strip()[:160]
        dims.append({"name": name, "score": score,
                     "color": item.get("color") or spec["color"],
                     "description": desc or "模型未给出说明"})
    if len(raw_dims) != 4:
        issues.append("维度数量为 %s（应为 4），已按四维度归一" % len(raw_dims))

    # 综合分：按规则恒等于加权分（指导书：综合 = 财务*40% + 经营*25% + 合规*35%）
    weighted = sum(d["score"] * WEIGHTS[d["name"]] for d in dims)
    total = _clamp_score(weighted)
    model_total = data.get("total_score")
    if model_total is not None:
        try:
            if abs(float(model_total) - weighted) > 2:
                issues.append("模型综合分 %s 与加权分 %.1f 不符，已按规则改用加权分"
                              % (model_total, weighted))
        except (TypeError, ValueError):
            issues.append("模型综合分非法，已改用加权分")

    # 等级：以分数为准，保证一致性
    level = level_of(total)
    model_level = str(data.get("risk_level") or "").strip().lower()
    if model_level not in LEVEL_TEXT:
        issues.append("risk_level 取值非法（%s），已按分数重新判定" % model_level)
    elif model_level != level:
        issues.append("等级 %s 与分数 %s 不一致，已按分数重新判定"
                      % (model_level, total))

    # 摘要：100 字以内
    summary = str(data.get("summary") or "").strip().replace("\n", " ")
    if not summary:
        summary = "模型未返回摘要"
        issues.append("摘要缺失，已补占位文本")
    if len(summary) > API_CONFIG["summary_limit"]:
        summary = summary[: API_CONFIG["summary_limit"] - 1] + "…"
        issues.append("摘要超过 100 字，已截断")

    # 建议：至少 1 条
    raw_sug = data.get("suggestions") or []
    if isinstance(raw_sug, str):
        raw_sug = [raw_sug]
    suggestions = [str(s).strip() for s in raw_sug if str(s).strip()][:6]
    if not suggestions:
        suggestions = ["开展尽调并核实企业公开信息", "关注司法涉诉与行政处罚记录",
                       "核实上下游集中度与回款账期", "持续跟踪舆情与经营异常"]
        issues.append("建议为空，已补默认建议")

    result = {
        "total_score": total,
        "risk_level": level,
        "risk_level_text": LEVEL_TEXT[level],
        "risk_level_color": LEVEL_COLOR[level],
        "summary": summary,
        "dimensions": dims,
        "suggestions": suggestions,
        "weighted_score": round(weighted, 1),
    }
    return result, issues


# ---------------------------------------------------------------------------
# 六、模拟结果（降级用，保证无 Key 时页面仍可用）
# ---------------------------------------------------------------------------
MOCK_BASE = {"互联网和软件": (62, 58, 45, 55), "制造业": (56, 50, 42, 40),
             "批发零售": (58, 62, 46, 48), "建筑": (70, 64, 60, 52),
             "教育": (66, 70, 62, 72), "房地产": (74, 68, 64, 60),
             "金融": (48, 44, 40, 46), "物流": (60, 54, 46, 44)}
SCALE_ADJ = {"large": -4, "medium": 0, "small": 5, "micro": 8}


def mock_llm_analysis(enterprise_name, description="", industry="", scale="small",
                      reason="未配置可用的 API Key"):
    """本地模拟：按行业与规模给的基准分 + 名称哈希做微小扰动，结果稳定可复现。"""
    base = None
    for key, val in MOCK_BASE.items():
        if key in (industry or ""):
            base = val
            break
    if base is None:
        base = (58, 56, 48, 50)
    adj = SCALE_ADJ.get(scale, 0)
    seed = int(hashlib.md5((enterprise_name or "").encode("utf-8")).hexdigest()[:6], 16)
    jitter = [(seed >> 0) % 7, (seed >> 3) % 7, (seed >> 6) % 7, (seed >> 9) % 7]
    scores = [(_clamp_score(base[i] + adj + jitter[i] - 3)) for i in range(4)]

    dims = []
    notes = ["模型未配置，以下为本地模拟结果", "行业基准：%s，规模调整：%+d 分" % (industry or "未提供", adj),
             "建议配置 API Key 后重新分析", "模拟结果不代表真实研判"]
    for i, spec in enumerate(DIMENSIONS):
        dims.append({"name": spec["name"], "score": scores[i], "color": spec["color"],
                     "description": "（模拟）%s" % notes[i]})
    weighted = sum(dims[i]["score"] * DIMENSIONS[i]["weight"] for i in range(4))
    total = _clamp_score(weighted)
    level = level_of(total)
    summary = "（模拟模式）%s属%s%s，%s；主要风险集中在%s。%s" % (
        enterprise_name or "该企业",
        {"large": "大型", "medium": "中型", "small": "小型", "micro": "微型"}.get(scale, "小型"),
        industry or "未注明行业",
        "整体风险中等" if level == "medium" else ("整体风险偏高" if level == "high" else "整体风险较低"),
        DIMENSION_NAMES[scores.index(max(scores))],
        "降级原因：%s。" % reason)
    result, _ = validate_result({
        "total_score": total, "risk_level": level, "summary": summary,
        "dimensions": dims,
        "suggestions": ["配置本账号 API Key 后重新分析，获得真实研判",
                        "工商与司法信息交叉核验，确认经营状态",
                        "核查是否存在行政处罚与失信记录",
                        "关注行业周期与上下游账期变化"],
    })
    return result


# ---------------------------------------------------------------------------
# 七、调用与降级
# ---------------------------------------------------------------------------
def _http_post(url, api_key, payload, timeout):
    """POST JSON，返回 (响应体 dict, 错误文本)。"""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", "Bearer " + api_key)
    req.add_header("Content-Type", "application/json")
    host = url.split("//")[-1].split("/")[0].split(":")[0]
    # 本机/内网模型服务绕过系统代理，避免被代理劫持
    proxy_bypass = host in ("127.0.0.1", "localhost", "0.0.0.0")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if proxy_bypass \
        else urllib.request.build_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:200]
        return None, "HTTP %s：%s" % (exc.code, body)
    except urllib.error.URLError as exc:
        return None, "网络不可达：%s" % exc.reason
    except Exception as exc:  # 超时、编码错误等
        return None, "调用失败：%s" % exc


def llm_risk_analysis(enterprise_name, credit_code="", description="", industry="",
                      scale="small", setting=None):
    """主入口：真实调用 → 解析 → 校验；任一步失败降级为模拟结果。

    返回 (result_dict, meta_dict)。meta 记录模式、模型、耗时、重试次数、校验问题，
    供页面展示与实训记录使用。
    """
    started = time.time()
    base_url = (getattr(setting, "base_url", "") or API_CONFIG["base_url"]).rstrip("/")
    api_key = (getattr(setting, "api_key", "") or API_CONFIG["api_key"]).strip()
    model = getattr(setting, "model_name", "") or API_CONFIG["model"]
    meta = {"mode": "mock", "model": model, "base_url": base_url,
            "attempts": 0, "elapsed_ms": 0, "error": "", "issues": [],
            "prompt_chars": 0, "truncated": False}

    user_prompt, truncated = build_user_prompt(enterprise_name, credit_code,
                                               description, industry, scale)
    meta["truncated"] = truncated
    meta["prompt_chars"] = len(SYSTEM_PROMPT) + len(user_prompt)

    if not api_key:
        result = mock_llm_analysis(enterprise_name, description, industry, scale,
                                   reason="未配置 API Key")
        meta["error"] = "未配置 API Key，已进入模拟模式"
        meta["elapsed_ms"] = int((time.time() - started) * 1000)
        return result, meta

    payload = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user_prompt}],
        "temperature": API_CONFIG["temperature"],
        "response_format": {"type": "json_object"},
        "max_tokens": 1200,
    }
    url = base_url + "/chat/completions"
    last_error = ""
    for attempt in range(API_CONFIG["max_retries"] + 1):
        meta["attempts"] = attempt + 1
        body, err = _http_post(url, api_key, payload, API_CONFIG["timeout"])
        if err:
            last_error = err
            # 401/403 重试无意义；429 与 5xx 退避后重试
            if "HTTP 401" in err or "HTTP 403" in err:
                break
            if attempt < API_CONFIG["max_retries"]:
                time.sleep(1.2 * (attempt + 1))
            continue
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            last_error = "响应缺少 choices[0].message.content"
            continue
        meta["usage"] = body.get("usage") or {}
        parsed = parse_llm_response(content)
        result, issues = validate_result(parsed)
        meta["issues"] = issues
        meta["mode"] = "real"
        meta["error"] = ""
        meta["elapsed_ms"] = int((time.time() - started) * 1000)
        return result, meta

    # 全部失败 → 降级
    result = mock_llm_analysis(enterprise_name, description, industry, scale,
                               reason=last_error or "模型调用失败")
    meta["error"] = last_error or "模型调用失败，已降级"
    meta["elapsed_ms"] = int((time.time() - started) * 1000)
    return result, meta