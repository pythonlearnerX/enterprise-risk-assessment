# -*- coding: utf-8 -*-
"""企业风险评估报告：生成 docx 并转 PDF（Word COM，无需联网）。"""
from __future__ import annotations

import base64
import os
import subprocess
import uuid
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from django.conf import settings


def _font(run, size=10.5, bold=False, color=None):
    run.font.name = "宋体"
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(size)
    run.font.bold = bold
    if color:
        run.font.color.rgb = RGBColor(*color)


def build_report_docx(ent, risk, calc, generated: str) -> Path:
    """生成报告 docx，返回路径（放在项目 _tmp/reports，ASCII 目录名）。"""
    outdir = Path(settings.BASE_DIR) / "_tmp" / "reports"
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / ("report_" + uuid.uuid4().hex[:8] + ".docx")

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(2)
    sec.bottom_margin = Cm(2)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(title.add_run("企业风险评估报告"), 20, True)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(sub.add_run("企业风险评估系统 · 四维 × 25 分 = 100 分"), 9,
          color=(0x6B, 0x72, 0x80))

    meta = [
        ("企业名称", ent.firm_name, "统一社会信用代码", ent.usc_code or "-"),
        ("法定代表人", ent.legal_rep or "-", "经营状态", ent.get_ope_status_display()),
        ("注册资本（万元）", f"{ent.reg_cap:.2f}" if ent.reg_cap else "-",
         "成立日期", ent.est_date.strftime("%Y-%m-%d") if ent.est_date else "-"),
    ]
    table = doc.add_table(rows=len(meta), cols=4)
    table.style = "Table Grid"
    for i, row in enumerate(meta):
        for j, value in enumerate(row):
            cell = table.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            _font(p.add_run(str(value)), 9, bold=(j % 2 == 0))

    h = doc.add_paragraph()
    _font(h.add_run("一、综合得分"), 12, True)
    score = doc.add_paragraph()
    score.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(score.add_run(f"{calc['total']:.2f}"), 30, True, (0x0F, 0x17, 0x2A))
    _font(score.add_run(f"   {calc['level_label']}"), 11, True, (0xB9, 0x1C, 0x1C))

    h2 = doc.add_paragraph()
    _font(h2.add_run("二、四维得分"), 12, True)
    t2 = doc.add_table(rows=1, cols=6)
    t2.style = "Table Grid"
    for j, label in enumerate(["维度", "满分", "原始三项", "平均", "维度得分", "权重"]):
        cell = t2.rows[0].cells[j]
        cell.text = ""
        _font(cell.paragraphs[0].add_run(label), 9, True)
    for key, d in calc["dimensions"].items():
        cells = t2.add_row().cells
        vals = [d["label"], "25", " / ".join(str(x) for x in d["raw"]),
                f"{d['average']:.2f}", f"{d['score']:.2f}", f"{d['weight']:.2f}"]
        for j, v in enumerate(vals):
            cells[j].text = ""
            _font(cells[j].paragraphs[0].add_run(v), 9, bold=(j == 4))

    h3 = doc.add_paragraph()
    _font(h3.add_run("三、12 项指标明细"), 12, True)
    pairs = [
        ("cai_1", "财务/近1年", risk.cai_1, "s_an_1", "经营/近1年", risk.s_an_1),
        ("cai_2", "财务/近2年", risk.cai_2, "s_an_2", "经营/近2年", risk.s_an_2),
        ("cai_3", "财务/近3年", risk.cai_3, "s_an_3", "经营/近3年", risk.s_an_3),
        ("li_an_1", "合规/近1年", risk.li_an_1, "zhi_1", "质量/近1年", risk.zhi_1),
        ("li_an_2", "合规/近2年", risk.li_an_2, "zhi_2", "质量/近2年", risk.zhi_2),
        ("li_an_3", "合规/近3年", risk.li_an_3, "zhi_3", "质量/近3年", risk.zhi_3),
    ]
    t3 = doc.add_table(rows=1, cols=4)
    t3.style = "Table Grid"
    for j, label in enumerate(["指标", "数值", "指标", "数值"]):
        t3.rows[0].cells[j].text = ""
        _font(t3.rows[0].cells[j].paragraphs[0].add_run(label), 9, True)
    for row in pairs:
        cells = t3.add_row().cells
        vals = [f"{row[0]}（{row[1]}）", str(row[2]), f"{row[3]}（{row[4]}）", str(row[5])]
        for j, v in enumerate(vals):
            cells[j].text = ""
            _font(cells[j].paragraphs[0].add_run(v), 9, bold=(j % 2 == 0))

    note = doc.add_paragraph()
    _font(note.add_run("评分口径："), 9, True)
    _font(note.add_run(
        "四维等权（各 25 分），综合得分 = 四维得分之和，范围 [0,100]。"
        "当前数据集按“风险点”口径（0–25，越大越危险）；若输入为事件次数，"
        "同一函数按扣分制计算：维度分 = max(0, 25 − 平均次数 × 1)。"), 9)

    dis = doc.add_paragraph()
    _font(dis.add_run("免责声明："), 9, True, (0xB9, 0x1C, 0x1C))
    _font(dis.add_run(
        "本报告由企业风险评估系统基于公开数据集自动生成，仅用于课程实训与内部研究，"
        "不构成任何投资、信贷、法律或商业决策建议。数据可能存在缺漏、滞后或口径差异，"
        "使用方应自行核实原始资料；因使用本报告产生的任何后果，系统与作者不承担责任。"), 8,
        color=(0x6B, 0x72, 0x80))

    foot = doc.add_paragraph()
    _font(foot.add_run(f"生成时间：{generated}    报告编号：ER-{risk.id:06d}"), 8,
          color=(0x6B, 0x72, 0x80))

    doc.save(path)
    return path


def docx_to_pdf(docx_path: Path) -> Path:
    """用 Word COM 把 docx 转 PDF，返回 PDF 路径。"""
    pdf_path = docx_path.with_suffix(".pdf")
    script = (
        "$ErrorActionPreference='Stop';"
        "$w=New-Object -ComObject Word.Application;"
        "$w.Visible=$false;"
        f"$d=$w.Documents.Open('{docx_path}');"
        f"$d.SaveAs([ref]'{pdf_path}',[ref]17);"
        "$d.Close();$w.Quit();"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded],
                   timeout=120, check=False, capture_output=True)
    return pdf_path