"""Build the course PDF (three passes so the table of contents has the right page numbers)."""

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.platypus import BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate, \
    Paragraph, Spacer, Table, TableStyle

import kit
from kit import (ACCENT, INK, MARGIN, MUTED, PAGE_H, PAGE_W, RULE, S, TEXT_W, P, box, bullets,
                 rich, table)
import part1, part2, part3, part4, part5

TITLE = "DeFi Risk from Scratch"
SUBTITLE = "A complete course on every blockchain and DeFi concept behind the DeFi Risk Dependency project"
OUT = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1] / "DeFi_Risk_from_Scratch.pdf")


def cover(c, doc):
    c.saveState()
    c.setFillColor(colors.HexColor("#14213d"))
    c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # a quiet dependency-graph motif
    import random
    rnd = random.Random(7)
    pts = [(rnd.uniform(40, PAGE_W - 40), rnd.uniform(PAGE_H * 0.08, PAGE_H * 0.42)) for _ in range(26)]
    c.setStrokeColor(colors.HexColor("#2f4a7d"))
    c.setLineWidth(0.6)
    for i, (x, y) in enumerate(pts):
        for (x2, y2) in pts[i + 1:i + 3]:
            c.line(x, y, x2, y2)
    for x, y in pts:
        c.setFillColor(colors.HexColor("#f4a261") if rnd.random() < 0.15 else colors.HexColor("#8ecae6"))
        c.circle(x, y, 3.2, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#8ecae6"))
    c.setFont("Sans-Bold", 10)
    c.drawString(MARGIN, PAGE_H - 120, "EPFL HACKATHON 2026 · BELEM CAPITAL CHALLENGE")
    c.setFillColor(colors.white)
    c.setFont("Sans-Bold", 40)
    c.drawString(MARGIN, PAGE_H - 175, "DeFi Risk")
    c.drawString(MARGIN, PAGE_H - 222, "from Scratch")
    c.setFont("Sans", 13.5)
    c.setFillColor(colors.HexColor("#d9e2f2"))
    y = PAGE_H - 262
    for line in ["A complete course on every blockchain and DeFi concept",
                 "behind the DeFi Risk Dependency project.",
                 "", "No prior knowledge assumed."]:
        c.drawString(MARGIN, y, line)
        y -= 20
    c.setFont("Sans", 9.5)
    c.setFillColor(colors.HexColor("#9fb0cc"))
    c.drawString(MARGIN, 40, "Based on the repository at commit ff651d1 (origin/main). Real numbers come "
                             "from the repository's cached data snapshots.")
    c.restoreState()


def page(c, doc):
    c.saveState()
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    c.line(MARGIN, PAGE_H - MARGIN + 8, PAGE_W - MARGIN, PAGE_H - MARGIN + 8)
    c.setFont("Sans", 7.8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN, PAGE_H - MARGIN + 12, TITLE)
    c.drawRightString(PAGE_W - MARGIN, 12 * 2.2, str(c.getPageNumber()))
    c.restoreState()


def toc_flowables(entries):
    out = [Paragraph("Contents", S["h1"]), Spacer(1, 6)]
    rows, styles = [], []
    for level, title, key, pageno in entries:
        st = S["toc1"] if level == 0 else S["toc2"]
        rows.append([Paragraph(f'<a href="#{key}">{rich(title)}</a>', st),
                     Paragraph(f'<a href="#{key}">{pageno}</a>',
                               st.clone("r", alignment=2, leftIndent=0))])
    if rows:
        t = Table(rows, colWidths=[TEXT_W - 40, 40])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0.5),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5)]))
        out.append(t)
    return out


def intro():
    s = [Paragraph("How to use this course", S["h1"]), kit.HRule(), Spacer(1, 6)]
    s += [P("This course is for anyone who wants to understand the **DeFi Risk Dependency** "
            "project, and the world it works in, **starting from zero**. You do not need to know "
            "what a blockchain is. Every technical term is defined the first time it appears and "
            "collected in the glossary (Appendix B).")]
    s += [P("**What the project does, in one paragraph.** A fund (Belem Capital) holds several "
            "DeFi positions, called **pockets**. For each one, the project automatically "
            "discovers what the position depends on (the blockchain, the protocols, the token "
            "issuers, the price oracles, the markets, the lenders). It then estimates how much "
            "money would be lost if any of them failed, and answers the risk manager's question: "
            "**STAY or EXIT**, and why. It runs on real, public data.")]
    s += [Paragraph("The path", S["h2"])]
    s += table([
        ["Part", "You will learn", "Chapters"],
        ["1. Blockchains from scratch", "Ledgers, blocks, keys, transactions, chains, smart "
                                        "contracts, admins, tokens, bridges.", "1-9"],
        ["2. DeFi building blocks", "Exchanges and AMMs, oracles, lending, vaults, Pendle, "
                                   "Ethena, perpetual futures; the dependency map.", "10-18"],
        ["3. Risk", "Incidents, probability, calibration on history, how losses spread through "
                    "the graph, liquidity.", "19-23"],
        ["4. Decisions", "The STAY / EXIT rule, the exit trigger for loans, the whole book.",
         "24-26"],
        ["5. The code", "Where each concept lives in the code, how to run and read the app, "
                        "limits.", "27-29"],
    ], [0.3, 0.55, 0.15])
    s += [Paragraph("The boxes", S["h2"])]
    s += [P("Coloured boxes appear throughout. Each colour has one job:")]
    for kind, text in [("idea", "The one thing to remember from a section."),
                       ("analogy", "A comparison with everyday life to build intuition."),
                       ("example", "A calculation done step by step. Redo it yourself."),
                       ("real", "Figures produced by the project's own code on real data."),
                       ("code", "Where the concept lives in the code."),
                       ("warn", "A trap, a subtlety, or a limit of the model."),
                       ("check", "Questions to test yourself. Answers in Appendix C.")]:
        label, border, bg = kit.BOXES[kind]
        t = Table([[Paragraph(f'<font color="{border.hexval()}"><b>{label.upper()}</b></font>',
                              S["boxbody"]), Paragraph(rich(text), S["boxbody"])]],
                  colWidths=[0.3 * TEXT_W, 0.7 * TEXT_W])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg),
                               ("LINEBEFORE", (0, 0), (0, -1), 3, border),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9),
                               ("TOPPADDING", (0, 0), (-1, -1), 4),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        s += [t, Spacer(1, 2.5)]
    s += [Paragraph("The running examples", S["h2"])]
    s += bullets([
        "**PT-sUSDe 26NOV2026**: a Pendle principal token on Ethereum, the hackathon's reference "
        "position (address `0x47ad…ef77e`).",
        "**Huma USDC Main**: a Morpho vault lending USDC against PST, a real-world-asset token "
        "bridged from Solana. It shows almost every danger at once.",
        "**The demo book**: six pockets of 1M USD each (PT-sUSDe, RockawayX, Huma, Belem RWA "
        "EURCV, Kamino Steakhouse HY USDC, Kamino RWA USDC). Figures come from the repository's "
        "cached snapshots; live runs will differ slightly, the reasoning will not.",
    ])
    return s


def story(toc_entries):
    s = [NextPageTemplate("body"), PageBreak()]
    s += toc_flowables(toc_entries)
    s += [PageBreak()]
    s += intro()
    for mod in (part1, part2, part3, part4, part5):
        s += mod.content()
    return s


def build(path, toc_entries):
    kit.TOC.clear()
    kit._n[0] = 0
    doc = BaseDocTemplate(path, pagesize=(PAGE_W, PAGE_H), leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=MARGIN, bottomMargin=MARGIN, title=TITLE, author="DeFi Risk team",
                          subject=SUBTITLE)
    frame = Frame(MARGIN, MARGIN, TEXT_W, PAGE_H - 2 * MARGIN, id="f", leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("cover", [frame], onPage=cover),
                          PageTemplate("body", [frame], onPage=page)])
    doc.build(story(toc_entries))
    return list(kit.TOC)


if __name__ == "__main__":
    entries = []
    for _ in range(3):
        entries = build(OUT, entries)
    print("built", OUT, len(entries), "toc entries")
