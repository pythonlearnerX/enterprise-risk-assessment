# -*- coding: utf-8 -*-
"""企业风险 PDF 报告（fpdf2 + 系统中文字体，纯 Python，无需 Word/浏览器）。"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\simkai.ttf",
    r"C:\Windows\Fonts\msyh.ttc",
]


def _font_path() -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise FileNotFoundError("未找到中文字体（simhei.ttf / simkai.ttf）")


class ReportPDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("CJK", size=8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "企业风险评估报告", align="R")
        self.ln(8)


def _cell(pdf, text, w, h=7, size=9, align="C", fill=False, color=(0, 0, 0)):
    pdf.set_font("CJK", size=size)
    pdf.set_text_color(255, 255, 255) if fill else pdf.set_text_color(*color)
    pdf.cell(w, h, text, border=1, align=align, fill=fill)


def build_risk_pdf(ent, risk, calc: dict, generated: str) -> bytes:
    pdf = ReportPDF(format="A4")
    pdf.add_font("CJK", "", _font_path())
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    # 标题
    pdf.set_font("CJK", size=20)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 12, "企业风险评估报告", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CJK", size=9)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 6, "企业风险评估系统 · 四维 × 25 分 = 100 分", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # 基本信息
    pdf.set_font("CJK", size=11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "一、企业基本信息", new_x="LMARGIN", new_y="NEXT")
    rows = [
        ("企业名称", ent.firm_name, "统一社会信用代码", ent.usc_code or "-"),
        ("法定代表人", ent.legal_rep or "-", "经营状态", ent.get_ope_status_display()),
        ("注册资本（万元）", f"{ent.reg_cap:.2f}" if ent.reg_cap else "-",
         "成立日期", ent.est_date.strftime("%Y-%m-%d") if ent.est_date else "-"),
    ]
    widths = (32, 58, 34, 56)
    for r in rows:
        _cell(pdf, r[0], widths[0], fill=True, color=(55, 65, 81))
        _cell(pdf, str(r[1]), widths[1], align="L")
        _cell(pdf, r[2], widths[2], fill=True, color=(55, 65, 81))
        _cell(pdf, str(r[3]), widths[3], align="L")
        pdf.ln(7)
    pdf.ln(3)

    # 综合得分
    pdf.set_font("CJK", size=12)
    pdf.cell(0, 7, "二、综合得分", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("CJK", size=30)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(38, 16, f"{calc['total']:.2f}", align="L")
    pdf.set_font("CJK", size=11)
    level_color = (185, 28, 28) if calc["level"] == "high" else ((180, 83, 9) if calc["level"] == "medium" else (22, 101, 52))
    pdf.set_text_color(*level_color)
    pdf.cell(30, 16, calc["level_label"], align="L", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # 四维
    pdf.set_font("CJK", size=12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "三、四维得分", new_x="LMARGIN", new_y="NEXT")
    heads = ("维度", "满分", "原始三项", "平均", "维度得分", "权重")
    widths = (34, 18, 48, 22, 34, 24)
    for h, w in zip(heads, widths):
        _cell(pdf, h, w, fill=True, color=(12, 74, 110))
    pdf.ln(7)
    for key, d in calc["dimensions"].items():
        vals = (d["label"], "25", " / ".join(str(x) for x in d["raw"]),
                f"{d['average']:.2f}", f"{d['score']:.2f}", f"{d['weight']:.2f}")
        for i, (v, w) in enumerate(zip(vals, widths)):
            _cell(pdf, v, w, size=8.5)
        pdf.ln(7)
    pdf.ln(3)

    # 12 项
    pdf.set_font("CJK", size=12)
    pdf.cell(0, 7, "四、12 项指标明细", new_x="LMARGIN", new_y="NEXT")
    pairs = [
        ("cai_1（财务/近1年）", risk.cai_1, "s_an_1（经营/近1年）", risk.s_an_1),
        ("cai_2（财务/近2年）", risk.cai_2, "s_an_2（经营/近2年）", risk.s_an_2),
        ("cai_3（财务/近3年）", risk.cai_3, "s_an_3（经营/近3年）", risk.s_an_3),
        ("li_an_1（合规/近1年）", risk.li_an_1, "zhi_1（质量/近1年）", risk.zhi_1),
        ("li_an_2（合规/近2年）", risk.li_an_2, "zhi_2（质量/近2年）", risk.zhi_2),
        ("li_an_3（合规/近3年）", risk.li_an_3, "zhi_3（质量/近3年）", risk.zhi_3),
    ]
    widths = (62, 28, 62, 28)
    for label, v, label2, v2 in pairs:
        _cell(pdf, label, widths[0], size=8.5, align="L")
        _cell(pdf, str(v), widths[1], size=8.5)
        _cell(pdf, label2, widths[2], size=8.5, align="L")
        _cell(pdf, str(v2), widths[3], size=8.5)
        pdf.ln(7)
    pdf.ln(3)

    # 口径
    pdf.set_font("CJK", size=8.5)
    pdf.set_text_color(75, 85, 99)
    pdf.multi_cell(0, 5, align="L",
                   text="评分口径：四维等权（各 25 分），综合得分 = 四维得分之和，范围 [0,100]。"
                   "当前数据集按“风险点”口径（0–25，越大越危险）；若输入为事件次数，"
                   "同一函数按扣分制计算：维度分 = max(0, 25 - 平均次数 × 1)。")
    pdf.ln(2)

    # 免责声明
    pdf.set_draw_color(220, 38, 38)
    pdf.set_text_color(185, 28, 28)
    pdf.set_font("CJK", size=9)
    pdf.cell(0, 6, "免责声明", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(107, 114, 128)
    pdf.set_font("CJK", size=7.5)
    pdf.multi_cell(0, 4.5,
                   "本报告由企业风险评估系统基于公开数据集自动生成，仅用于课程实训与内部研究，"
                   "不构成任何投资、信贷、法律或商业决策建议。数据可能存在缺漏、滞后或口径差异，"
                   "使用方应自行核实原始资料；因使用本报告产生的任何后果，系统与作者不承担责任。")
    pdf.ln(2)

    pdf.set_font("CJK", size=8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"生成时间：{generated}    报告编号：ER-{risk.id:06d}", align="L")
    return bytes(pdf.output())