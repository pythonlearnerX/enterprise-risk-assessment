# -*- coding: utf-8 -*-
"""NLP 风险识别微服务（项目 15）。

独立于 Django 运行，提供两个接口：
  GET  /health   -> 探活
  POST /analyze  -> 文本风险识别（四类词库 + 加权评分）

设计要点
--------
1. 绑定 0.0.0.0 而不是 127.0.0.1：容器的 127.0.0.1 是容器自己，宿主机访问不到。
2. 关键词直接用「原文包含」匹配，不依赖分词结果：像「资金链断裂」「立案调查」这类多字词
   会被 jieba 切碎，用分词结果比对会漏匹配。jieba 只用于统计词数。
3. 每类得分封顶 100，总分为加权和（合规 40%、财务 30%、经营 20%、舆情 10%）。
4. 等级：>=60 高、>=30 中、其余低。
"""
import os

import jieba
from flask import Flask, jsonify, request

app = Flask(__name__)

RISK_DICT = {
    "financial": {
        "亏损": 10, "利润下滑": 9, "资金链断裂": 10, "债务违约": 10,
        "财务造假": 10, "资不抵债": 10, "坏账": 8, "欠款": 7, "负债": 7,
    },
    "operation": {
        "裁员": 9, "停产": 9, "倒闭": 10, "破产": 10, "业绩下滑": 8,
        "市场份额": 6, "供应链": 6, "高管离职": 7,
    },
    "compliance": {
        "处罚": 9, "罚款": 8, "立案调查": 10, "证监会": 10, "违法": 10,
        "违规": 9, "诉讼": 8, "行政处罚": 9, "失信": 10, "被执行人": 9,
    },
    "public_opinion": {
        "曝光": 8, "投诉": 7, "维权": 8, "举报": 9, "丑闻": 10,
        "负面新闻": 9, "安全事故": 10, "环境污染": 9,
    },
}

# 中文类别名，返回体里同时给英文键，前端按中文标签着色
CATEGORY_LABELS = {
    "financial": "财务",
    "operation": "经营",
    "compliance": "合规",
    "public_opinion": "舆情",
}

WEIGHTS = {"compliance": 0.4, "financial": 0.3, "operation": 0.2, "public_opinion": 0.1}


def analyze_text(text):
    """词库匹配 + 加权评分，返回结构化结果。"""
    if not text or not text.strip():
        return {"error": "文本为空"}

    words = list(jieba.cut(text))
    result = {}
    for category, word_dict in RISK_DICT.items():
        hits, score = [], 0
        for keyword, weight in word_dict.items():
            if keyword in text:                 # 原文匹配，避免分词过细
                hits.append(keyword)
                score = min(score + weight, 100)  # 每类封顶 100
        result[category] = {
            "score": round(score, 1),
            "keywords": hits[:10],
            "count": len(hits),
            "label": CATEGORY_LABELS[category],
        }

    overall = round(sum(result[k]["score"] * w for k, w in WEIGHTS.items()), 1)
    level = "high" if overall >= 60 else ("medium" if overall >= 30 else "low")
    return {
        "total_score": overall,
        "risk_level": level,
        "details": result,
        "word_count": len(words),
        "keywords_found": sum(len(v["keywords"]) for v in result.values()),
    }


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "nlp-risk-analyzer"})


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True, silent=True) or {}
    return jsonify(analyze_text(data.get("text", "")))


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "接口不存在", "endpoints": ["/health", "/analyze"]}), 404


if __name__ == "__main__":
    jieba.initialize()          # 预热词典，避免首次调用很慢
    port = int(os.environ.get("NLP_PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)