"""Layout kit for the course PDF: fonts, styles, callout boxes, tables, diagrams."""

import math
import re

from reportlab.graphics.shapes import (Drawing, Line, PolyLine, Polygon, Rect, String, Circle)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, KeepTogether, PageBreak, Paragraph, Spacer, Table,
                                TableStyle, Flowable)

SUP = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("Sans", SUP + "Arial.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", SUP + "Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Italic", SUP + "Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans-BoldItalic", SUP + "Arial Bold Italic.ttf"))
pdfmetrics.registerFont(TTFont("Uni", SUP + "Arial Unicode.ttf"))
pdfmetrics.registerFont(TTFont("Mono", "/System/Library/Fonts/Menlo.ttc", subfontIndex=0))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans-Italic",
                              boldItalic="Sans-BoldItalic")

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
TEXT_W = PAGE_W - 2 * MARGIN

INK = colors.HexColor("#1d2433")
MUTED = colors.HexColor("#5b6475")
ACCENT = colors.HexColor("#2a5bd7")
RULE = colors.HexColor("#d5dae3")

# Callout kinds: (label, border, background)
BOXES = {
    "idea": ("Key idea", colors.HexColor("#2a5bd7"), colors.HexColor("#eef3fd")),
    "analogy": ("Everyday analogy", colors.HexColor("#1f8a5b"), colors.HexColor("#ecf7f1")),
    "example": ("Worked example", colors.HexColor("#b26a00"), colors.HexColor("#fdf5e8")),
    "code": ("In the project's code", colors.HexColor("#6b4fbb"), colors.HexColor("#f3f0fb")),
    "warn": ("Watch out", colors.HexColor("#c0392b"), colors.HexColor("#fcefed")),
    "check": ("Check yourself", colors.HexColor("#3d4b63"), colors.HexColor("#f2f4f8")),
    "real": ("Real numbers from this project", colors.HexColor("#0b7f8c"), colors.HexColor("#e9f6f7")),
}

S = {
    "body": ParagraphStyle("body", fontName="Sans", fontSize=10.2, leading=14.6, textColor=INK,
                           spaceAfter=6),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=8.8, leading=12, textColor=MUTED),
    "bullet": ParagraphStyle("bullet", fontName="Sans", fontSize=10.2, leading=14.4, textColor=INK,
                             leftIndent=14, bulletIndent=3, spaceAfter=2.5),
    "part": ParagraphStyle("part", fontName="Sans-Bold", fontSize=30, leading=36, textColor=ACCENT,
                           spaceAfter=10),
    "partsub": ParagraphStyle("partsub", fontName="Sans", fontSize=13, leading=19, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName="Sans-Bold", fontSize=19, leading=24, textColor=INK,
                         spaceBefore=4, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Sans-Bold", fontSize=13.2, leading=17, textColor=ACCENT,
                         spaceBefore=10, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Sans-Bold", fontSize=10.8, leading=14.5, textColor=INK,
                         spaceBefore=6, spaceAfter=3),
    "boxlabel": ParagraphStyle("boxlabel", fontName="Sans-Bold", fontSize=8.4, leading=11,
                               textColor=INK, spaceAfter=3),
    "boxbody": ParagraphStyle("boxbody", fontName="Sans", fontSize=9.7, leading=13.6, textColor=INK,
                              spaceAfter=3),
    "boxbullet": ParagraphStyle("boxbullet", fontName="Sans", fontSize=9.7, leading=13.4,
                                textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "formula": ParagraphStyle("formula", fontName="Uni", fontSize=10.6, leading=16, textColor=INK,
                              alignment=TA_CENTER),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=11, textColor=INK),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=8.9, leading=11.6, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Sans-Bold", fontSize=8.9, leading=11.6,
                            textColor=colors.white),
    "toc1": ParagraphStyle("toc1", fontName="Sans-Bold", fontSize=10.5, leading=15, textColor=INK,
                           spaceBefore=5),
    "toc2": ParagraphStyle("toc2", fontName="Sans", fontSize=9.8, leading=13.4, textColor=INK,
                           leftIndent=14),
    "gterm": ParagraphStyle("gterm", fontName="Sans", fontSize=9.4, leading=12.6, textColor=INK,
                            leftIndent=10, firstLineIndent=-10, spaceAfter=3.2),
    "caption": ParagraphStyle("caption", fontName="Sans-Italic", fontSize=8.6, leading=11.4,
                              textColor=MUTED, alignment=TA_CENTER, spaceAfter=8),
}

# Symbols the text font lacks are drawn with Arial Unicode.
_UNI = "✓"


def rich(text: str) -> str:
    """Light markup: **bold**, *italic*, `code`; wraps rare glyphs in the Unicode font."""
    text = re.sub(r"`([^`]+)`", r'<font name="Mono" size="8.8">\1</font>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    for ch in _UNI:
        text = text.replace(ch, f'<font name="Uni">{ch}</font>')
    return text


def P(text, style="body"):
    return Paragraph(rich(text), S[style])


def bullets(items, style="bullet"):
    return [Paragraph(rich(t), S[style], bulletText="•") for t in items]


def numbered(items, style="bullet"):
    return [Paragraph(rich(t), S[style], bulletText=f"{i}.") for i, t in enumerate(items, 1)]


def formula(text):
    return [Spacer(1, 2), Paragraph(rich(text), S["formula"]), Spacer(1, 6)]


def box(kind, *content):
    """A callout. Content: strings (paragraphs), lists (bullets) or flowables."""
    label, border, bg = BOXES[kind]
    inner = [Paragraph(label.upper(), ParagraphStyle("bl", parent=S["boxlabel"], textColor=border))]
    for c in content:
        if isinstance(c, str):
            inner.append(Paragraph(rich(c), S["boxbody"]))
        elif isinstance(c, list):
            inner += [Paragraph(rich(t), S["boxbullet"], bulletText="•") for t in c]
        else:
            inner.append(c)
    t = Table([[inner]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, border),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [Spacer(1, 3), t, Spacer(1, 8)]


def code(text):
    lines = text.strip("\n").split("\n")
    paras = [Paragraph(l.replace("&", "&amp;").replace("<", "&lt;").replace(" ", "&nbsp;") or "&nbsp;",
                       S["code"]) for l in lines]
    t = Table([[paras]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f6f8")),
                           ("BOX", (0, 0), (-1, -1), 0.5, RULE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 6),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return [t, Spacer(1, 8)]


def table(rows, widths=None, header=True):
    """rows: list of lists of strings. widths: fractions of the text width."""
    n = len(rows[0])
    widths = widths or [1 / n] * n
    data = []
    for i, r in enumerate(rows):
        st = "cellh" if header and i == 0 else "cell"
        data.append([Paragraph(rich(str(c)), S[st]) for c in r])
    t = Table(data, colWidths=[w * TEXT_W for w in widths], repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
             ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#33415c"))]
        style += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f6f8fb"))
                  for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return [Spacer(1, 2), t, Spacer(1, 9)]


# --- headings that feed the table of contents -------------------------------

class Anchor(Flowable):
    """Zero-size flowable that records a TOC entry and a PDF outline bookmark."""

    def __init__(self, level, title, key):
        super().__init__()
        self.level, self.title, self.key = level, title, key
        self.width = self.height = 0

    def draw(self):
        c = self.canv
        c.bookmarkPage(self.key)
        c.addOutlineEntry(self.title, self.key, level=self.level, closed=self.level > 0)
        TOC.append((self.level, self.title, self.key, c.getPageNumber()))


TOC: list = []
_n = [0]


def _key():
    _n[0] += 1
    return f"k{_n[0]}"


def part(num, title, subtitle):
    k = _key()
    return [PageBreak(), Spacer(1, 120), Anchor(0, f"Part {num}. {title}", k),
            Paragraph(f"PART {num}", ParagraphStyle("pn", parent=S["partsub"], textColor=ACCENT,
                                                     fontName="Sans-Bold")),
            Paragraph(title, S["part"]), Paragraph(rich(subtitle), S["partsub"]), PageBreak()]


def chapter(num, title, new_page=True):
    k = _key()
    head = [Anchor(1, f"{num}. {title}", k), Paragraph(f"{num}. {title}", S["h1"]),
            HRule(), Spacer(1, 4)]
    return [CondPageBreak(260 if new_page else 120)] + head


def section(title):
    return [CondPageBreak(70), Paragraph(rich(title), S["h2"])]


def sub(title):
    return [CondPageBreak(50), Paragraph(rich(title), S["h3"])]


class HRule(Flowable):
    def __init__(self, width=TEXT_W, color=RULE):
        super().__init__()
        self.width, self.height, self.color = width, 1, color

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(0.8)
        self.canv.line(0, 0, self.width, 0)


# --- diagrams ----------------------------------------------------------------

PALETTE = {
    "position": "#f4a261", "chain": "#8ecae6", "protocol": "#90be6d", "asset": "#ffd166",
    "issuer": "#f28482", "oracle": "#cdb4db", "market": "#a8dadc", "lending": "#b5838d",
    "venue": "#adb5bd", "vault": "#e9c46a", "admin": "#ffafcc", "plain": "#e8ecf3",
    "good": "#bfe5c9", "bad": "#f6c6c0", "white": "#ffffff", "blue": "#cfe0fb",
}


def _wrap(text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(t, font, size) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _arrow(d, x1, y1, x2, y2, color=INK, width=1.0, label=None, dashed=False, label_dx=0,
           label_dy=0, size=7.2):
    ang = math.atan2(y2 - y1, x2 - x1)
    L = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width)
    if dashed:
        L.strokeDashArray = [3, 2]
    d.add(L)
    h = 5.5
    d.add(Polygon([x2, y2, x2 - h * math.cos(ang - 0.4), y2 - h * math.sin(ang - 0.4),
                   x2 - h * math.cos(ang + 0.4), y2 - h * math.sin(ang + 0.4)],
                  fillColor=color, strokeColor=color, strokeWidth=0.5))
    if label:
        mx, my = (x1 + x2) / 2 + label_dx, (y1 + y2) / 2 + label_dy
        w = pdfmetrics.stringWidth(label, "Sans", size) + 4
        d.add(Rect(mx - w / 2, my - 3, w, size + 3, fillColor=colors.white, strokeColor=None))
        d.add(String(mx, my, label, fontName="Sans", fontSize=size, fillColor=MUTED,
                     textAnchor="middle"))


def _edge_point(b, tx, ty):
    """Point on the border of box b toward (tx, ty)."""
    x, y, w, h = b
    cx, cy = x + w / 2, y + h / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else float("inf")
    sy = (h / 2) / abs(dy) if dy else float("inf")
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def diagram(width, height, boxes, arrows=(), texts=(), caption=None, scale_to_text=True):
    """boxes: {key: (x, y, w, h, label, color)}; coordinates in points, origin bottom-left.
    arrows: (from, to, label) or (from, to, label, opts dict). texts: (x, y, text, opts)."""
    d = Drawing(width, height)
    geo = {}
    for k, (x, y, w, h, label, col) in boxes.items():
        fill = colors.HexColor(PALETTE.get(col, col))
        d.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=colors.HexColor("#4a5568"),
                   strokeWidth=0.7))
        size = 8.2 if h >= 26 else 7.4
        lines = []
        for part_ in label.split("\n"):
            lines += _wrap(part_, "Sans", size, w - 8)
        total = len(lines) * (size + 1.6)
        top = y + h / 2 + total / 2 - size + 0.5
        for i, ln in enumerate(lines):
            bold = i == 0 and "\n" in label
            d.add(String(x + w / 2, top - i * (size + 1.6), ln, fontName="Sans-Bold" if bold else "Sans",
                         fontSize=size, fillColor=INK, textAnchor="middle"))
        geo[k] = (x, y, w, h)
    for a in arrows:
        src, dst, label = a[0], a[1], a[2]
        o = a[3] if len(a) > 3 else {}
        bs, bd = geo[src], geo[dst]
        cs = (bs[0] + bs[2] / 2, bs[1] + bs[3] / 2)
        cd = (bd[0] + bd[2] / 2, bd[1] + bd[3] / 2)
        x1, y1 = _edge_point(bs, *cd)
        x2, y2 = _edge_point(bd, *cs)
        _arrow(d, x1, y1, x2, y2, color=colors.HexColor(o.get("color", "#2d3748")),
               label=label, dashed=o.get("dashed", False), label_dx=o.get("dx", 0),
               label_dy=o.get("dy", 0))
    for t in texts:
        x, y, s = t[0], t[1], t[2]
        o = t[3] if len(t) > 3 else {}
        d.add(String(x, y, s, fontName=o.get("font", "Sans"), fontSize=o.get("size", 8),
                     fillColor=colors.HexColor(o.get("color", "#5b6475")),
                     textAnchor=o.get("anchor", "middle")))
    out = [Spacer(1, 4), d]
    if caption:
        out.append(Paragraph(rich(caption), S["caption"]))
    else:
        out.append(Spacer(1, 8))
    return [KeepTogether(out)]


def plot(width, height, series, xlim, ylim, xlabel, ylabel, xticks, yticks, marks=(), caption=None,
         xfmt=str, yfmt=str, shade=None):
    """Simple line chart. series: [(points, color, label)]. marks: [(x, y, text)] dots with labels.
    shade: (x0, x1, color) vertical band."""
    d = Drawing(width, height)
    L, B, R, T = 48, 32, 14, 24
    pw, ph = width - L - R, height - B - T

    def X(v):
        return L + (v - xlim[0]) / (xlim[1] - xlim[0]) * pw

    def Y(v):
        return B + (min(max(v, ylim[0]), ylim[1]) - ylim[0]) / (ylim[1] - ylim[0]) * ph

    if shade:
        d.add(Rect(X(shade[0]), B, X(shade[1]) - X(shade[0]), ph,
                   fillColor=colors.HexColor(shade[2]), strokeColor=None))
    for t in yticks:
        d.add(Line(L, Y(t), L + pw, Y(t), strokeColor=colors.HexColor("#e6e9ef"), strokeWidth=0.5))
        d.add(String(L - 5, Y(t) - 3, yfmt(t), fontName="Sans", fontSize=7.4, fillColor=MUTED,
                     textAnchor="end"))
    for t in xticks:
        d.add(String(X(t), B - 12, xfmt(t), fontName="Sans", fontSize=7.4, fillColor=MUTED,
                     textAnchor="middle"))
    d.add(Line(L, B, L + pw, B, strokeColor=MUTED, strokeWidth=0.7))
    d.add(Line(L, B, L, B + ph, strokeColor=MUTED, strokeWidth=0.7))
    d.add(String(L + pw / 2, 4, xlabel, fontName="Sans", fontSize=8, fillColor=INK,
                 textAnchor="middle"))
    ys = String(0, 0, ylabel, fontName="Sans", fontSize=8, fillColor=INK, textAnchor="middle")
    from reportlab.graphics.shapes import Group
    g = Group(ys)
    g.translate(11, B + ph / 2)
    g.rotate(90)
    d.add(g)
    lx, ly = L, height - 10
    for pts, col, label in series:
        flat = []
        for x, y in pts:
            flat += [X(x), Y(y)]
            if y > ylim[1]:  # stop where the curve leaves the chart
                break
        d.add(PolyLine(flat, strokeColor=colors.HexColor(col), strokeWidth=1.8))
        if label:
            d.add(Line(lx, ly + 3, lx + 14, ly + 3, strokeColor=colors.HexColor(col),
                       strokeWidth=2))
            d.add(String(lx + 18, ly, label, fontName="Sans", fontSize=7.6, fillColor=INK))
            lx += 28 + pdfmetrics.stringWidth(label, "Sans", 7.6)
    for m in marks:
        x, y, text = m[:3]
        dx, dy, anchor = (m[3], m[4], m[5]) if len(m) > 3 else (5, 4, "start")
        d.add(Circle(X(x), Y(y), 2.8, fillColor=INK, strokeColor=colors.white, strokeWidth=0.6))
        if not text:
            continue
        w = pdfmetrics.stringWidth(text, "Sans", 7.4)
        x0 = X(x) + dx - (w if anchor == "end" else 0)
        d.add(Rect(x0 - 1.5, Y(y) + dy - 2, w + 3, 10, fillColor=colors.white, strokeColor=None,
                   fillOpacity=0.85))
        d.add(String(X(x) + dx, Y(y) + dy, text, fontName="Sans", fontSize=7.4, fillColor=INK,
                     textAnchor=anchor))
    out = [Spacer(1, 4), d]
    out.append(Paragraph(rich(caption), S["caption"]) if caption else Spacer(1, 8))
    return [KeepTogether(out)]


def glossary(entries):
    out = []
    for term, definition in entries:
        out.append(Paragraph(f"<b>{rich(term)}</b>: {rich(definition)}", S["gterm"]))
    return out
