# -*- coding: utf-8 -*-
"""纯 Python 生成 SVG 图表（无第三方依赖，离线可用）。"""
from html import escape

FONT = "'Times New Roman','SimSun',serif"
NAVY = "#1F3A5F"
BLUE = "#4E6E8E"
TEAL = "#7FA6A0"
OCHRE = "#C9A66B"
GREY = "#6B7280"
PALETTE = [BLUE, TEAL, OCHRE, "#B08A8A", "#8E8E8E"]


def _svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" font-family="{FONT}">'
            f'<rect width="100%" height="100%" fill="#ffffff"/>{body}</svg>')


def _title(text, width):
    return (f'<text x="{width/2}" y="30" text-anchor="middle" font-size="16" '
            f'fill="{NAVY}" font-weight="bold">{escape(text)}</text>')


def bar_chart(labels, values, title, width=640, height=380, color=BLUE):
    left, right, top, bottom = 150, 80, 56, 40
    plot_w = width - left - right
    n = max(len(values), 1)
    row_h = (height - top - bottom) / n
    vmax = (max(values) * 1.06) if values and max(values) > 0 else 1
    parts = [_title(title, width)]
    for i, (lab, val) in enumerate(zip(labels, values)):
        y = top + i * row_h
        bh = row_h * 0.55
        bw = plot_w * val / vmax
        parts.append(f'<text x="{left-10}" y="{y+bh*0.8}" text-anchor="end" font-size="12" fill="#333">{escape(str(lab))}</text>')
        parts.append(f'<rect x="{left}" y="{y}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{left+bw+8}" y="{y+bh*0.8}" font-size="12" fill="{GREY}">{val}</text>')
    parts.append(f'<line x1="{left}" y1="{top-8}" x2="{left}" y2="{height-bottom+6}" stroke="#D5DCE6"/>')
    return _svg(width, height, "".join(parts))


def pie_chart(items, title, width=520, height=380):
    total = sum(v for _, v in items) or 1
    cx, cy, r = width * 0.36, height * 0.56, 110
    parts = [_title(title, width)]
    start = -90.0
    import math
    for i, (lab, val) in enumerate(items):
        angle = 360.0 * val / total
        end = start + angle
        large = 1 if angle > 180 else 0
        x1 = cx + r * math.cos(math.radians(start))
        y1 = cy + r * math.sin(math.radians(start))
        x2 = cx + r * math.cos(math.radians(end))
        y2 = cy + r * math.sin(math.radians(end))
        color = PALETTE[i % len(PALETTE)]
        parts.append(f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large} 1 {x2:.1f},{y2:.1f} Z" '
                     f'fill="{color}" opacity="0.88"/>')
        ly = 90 + i * 28
        parts.append(f'<rect x="{width-190}" y="{ly-10}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{width-172}" y="{ly}" font-size="12" fill="#333">{escape(str(lab))} '
                     f'{val}（{val/total:.1%}）</text>')
        start = end
    return _svg(width, height, "".join(parts))


def hist_chart(bins, counts, title, width=640, height=360, color=TEAL):
    left, right, top, bottom = 56, 30, 56, 56
    plot_w = width - left - right
    plot_h = height - top - bottom
    vmax = max(counts) if counts and max(counts) > 0 else 1
    bw = plot_w / max(len(counts), 1) * 0.7
    gap = plot_w / max(len(counts), 1)
    parts = [_title(title, width)]
    for i, (lab, val) in enumerate(zip(bins, counts)):
        h = plot_h * val / vmax
        x = left + i * gap + (gap - bw) / 2
        y = top + plot_h - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{color}" opacity="0.85"/>')
        parts.append(f'<text x="{x+bw/2:.1f}" y="{y-6:.1f}" text-anchor="middle" font-size="11" fill="{GREY}">{val}</text>')
        parts.append(f'<text x="{x+bw/2:.1f}" y="{top+plot_h+18}" text-anchor="middle" font-size="11" fill="#333">{escape(str(lab))}</text>')
    parts.append(f'<line x1="{left}" y1="{top+plot_h}" x2="{width-right}" y2="{top+plot_h}" stroke="#D5DCE6"/>')
    return _svg(width, height, "".join(parts))