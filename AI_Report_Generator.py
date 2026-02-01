# ================================
# File: ai_report_generator.py
# ================================

import os
import json
import tempfile
from typing import Dict, Any, TypedDict, Optional

import pandas as pd

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image as RLImage,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

# Plotly export (requires kaleido)
import plotly.io as pio

# LangGraph
from langgraph.graph import StateGraph, END

# OpenAI
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

# =========================================================
# Visual theme (tweak here)
# =========================================================
THEME = {
    "brand": colors.HexColor("#2457C5"),     # header bar
    "brand2": colors.HexColor("#0EA5A4"),    # accent
    "text": colors.HexColor("#111827"),
    "muted": colors.HexColor("#6B7280"),
    "bg": colors.HexColor("#F6F7FB"),
    "card": colors.HexColor("#F3F4F6"),
    "table_header": colors.HexColor("#E8EEF9"),
    "table_grid": colors.HexColor("#D1D5DB"),
}
PAYER_COLOR_MAP = {
    "Medicare": "#438CF3",
    "Medicaid": "#A2F2FC",
    "Blue Cross Blue Shield": "#35B76B",
    "Dual Eligible": "#F28B82",
    "Humana": "#8A6FD1",
    "Other / Unknown": "#9CA3AF",
}


PLOTLY_TEMPLATE = "plotly_white"
PLOTLY_COLORWAY = [
    PAYER_COLOR_MAP["Medicare"],
    PAYER_COLOR_MAP["Medicaid"],
    PAYER_COLOR_MAP["Blue Cross Blue Shield"],
    PAYER_COLOR_MAP["Dual Eligible"],
    PAYER_COLOR_MAP["Humana"],
]


# =========================================================
# Prompts
# =========================================================
SYSTEM_PROMPT = """
You are a healthcare analytics reporting assistant.
You must be accurate and grounded ONLY in the provided JSON data.

Hard rules:
- Do NOT invent numbers, payer names, medication names, or facts.
- If a detail is missing in JSON, say: "Not available in dashboard output".
- Keep language concise, professional, and report-like.
- Do not mention prompts, tooling, or that you are an AI.
""".strip()


def _user_prompt(report_type: str, payload: Dict[str, Any]) -> str:
    if "Operations" in report_type:
        return f"""
Generate content for a TWO-PAGE PDF report titled:
"Medication Coverage & Payer Analytics — Operations Drilldown"

Use ONLY the JSON below.

Output format (exact headings):
1) TL;DR (5 bullets)
2) What Stands Out (5 bullets)
3) Payer-Specific Flags (one mini-section per payer present in JSON):
   - PAYER: <name>
     - Issue Summary (2 bullets)
     - High-Risk Medications (up to 3 meds: include code + name)
4) Action Checklist (7 bullets)

Constraints:
- High-Risk Medications must be chosen ONLY from coverage_review_sample/top_oop_meds.
- If payer not present, say "Not available in dashboard output".
- Keep it actionable for payer analytics, contracting, pharmacy ops.

JSON:
{json.dumps(payload, indent=2)}
""".strip()

    return f"""
Generate content for a TWO-PAGE PDF report titled:
"Medication Coverage & Payer Analytics — Executive Summary"

Use ONLY the JSON below.

Output format (exact headings):
1) TL;DR (5 bullets)
2) KPI Snapshot (1 short paragraph — include date range + payers reviewed)
3) Biggest Coverage Gaps (3 bullets)
4) Top Patient Burden Drivers (3 bullets)
5) Recommended Actions (5 bullets)

Constraints:
- Bullets must be short and specific.
- Use payer/med names EXACTLY as in JSON.
- Focus on cost/coverage analytics and operational actions.

JSON:
{json.dumps(payload, indent=2)}
""".strip()


# =========================================================
# OpenAI client
# =========================================================
def call_openai_text(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> str:
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content


# =========================================================
# Payload packing
# =========================================================
def pack_payload(
    meta: Dict[str, Any],
    kpis: Dict[str, Any],
    payer_agg: pd.DataFrame,
    med_oop: pd.DataFrame,
    review_tbl: pd.DataFrame,
    max_review_rows: int | None = None,  # if None => send all
) -> Dict[str, Any]:
    payer_summary = payer_agg.copy()
    if "COVERAGE_PCT" in payer_summary.columns:
        payer_summary = payer_summary.sort_values("COVERAGE_PCT")

    med_cols = [c for c in ["MEDICATION_CODE", "MEDICATION_NAME", "TOTAL_OOP", "TOTAL_RX"] if c in med_oop.columns]
    med_small = med_oop[med_cols].copy()

    review_cols = [
        "PAYER_NAME",
        "MEDICATION_CODE",
        "MEDICATION_NAME",
        "PRESCRIPTIONS",
        "TOTAL_COST",
        "PAYER_PAID",
        "PATIENT_PAID",
        "COVERAGE_PCT",
    ]
    review_small = review_tbl[[c for c in review_cols if c in review_tbl.columns]].copy()

    if "COVERAGE_PCT" in review_small.columns and "PATIENT_PAID" in review_small.columns:
        review_small = review_small.sort_values(["COVERAGE_PCT", "PATIENT_PAID"], ascending=[True, False])

    # If caller supplies limit, apply; else send all rows
    if max_review_rows is not None:
        review_small = review_small.head(max_review_rows)

    return {
        "meta": meta,
        "kpis": kpis,
        "payer_coverage_summary": payer_summary.to_dict(orient="records"),
        "top_oop_meds": med_small.to_dict(orient="records"),
        "coverage_review_sample": review_small.to_dict(orient="records"),
    }


# =========================================================
# Plotly aesthetics + export
# =========================================================
def _apply_plotly_style(fig, title: str | None = None):
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        colorway=PLOTLY_COLORWAY,
        title=title or fig.layout.title.text,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=40, r=30, t=60, b=45),
        font=dict(size=12),
    )
    # make axes cleaner if they exist
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0.08)", zeroline=False)
    return fig


def _fig_to_png_bytes(fig) -> bytes:
    """
    Exports a plotly figure to PNG bytes.
    Requires: pip install -U kaleido
    """
    try:
        return fig.to_image(format="png", scale=2)
    except Exception as e:
        raise RuntimeError(
            "Plotly PNG export failed. Install kaleido:\n"
            "  pip install -U kaleido\n"
            f"Original error: {e}"
        )


# =========================================================
# ReportLab helpers (styles + header/footer)
# =========================================================
def _money(x: Any) -> str:
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return str(x)


def _pct(x: Any) -> str:
    try:
        return f"{float(x):.2f}%"
    except Exception:
        return str(x)


def _build_styles():
    base = getSampleStyleSheet()

    H1 = ParagraphStyle(
        "H1",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=THEME["text"],
        spaceAfter=10,
    )
    H2 = ParagraphStyle(
        "H2",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        textColor=THEME["brand"],
        spaceBefore=10,
        spaceAfter=6,
    )
    BODY = ParagraphStyle(
        "BODY",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=THEME["text"],
    )
    MUTED = ParagraphStyle(
        "MUTED",
        parent=BODY,
        textColor=THEME["muted"],
        fontSize=9,
    )
    BULLET = ParagraphStyle(
        "BULLET",
        parent=BODY,
        leftIndent=14,
        bulletIndent=6,
        spaceBefore=1,
        spaceAfter=1,
    )
    return H1, H2, BODY, MUTED, BULLET


def _draw_header_footer(canvas, doc, meta: Dict[str, Any]):
    # header bar
    canvas.saveState()
    w, h = letter

    canvas.setFillColor(THEME["brand"])
    canvas.rect(0, h - 52, w, 52, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(36, h - 34, "Medication Coverage & Payer Analytics")

    canvas.setFont("Helvetica", 9)
    canvas.drawString(
        36,
        h - 48,
        f"Date Range: {meta.get('start_date')} → {meta.get('end_date')}  |  Report: {meta.get('report_type', 'N/A')}",
    )

    # footer
    canvas.setFillColor(THEME["muted"])
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(36, 22, "Generated from dashboard aggregates (selected filters).")
    canvas.drawRightString(w - 36, 22, f"Page {doc.page}")

    canvas.restoreState()


def _kpi_cards(kpis: Dict[str, Any], BODY: ParagraphStyle, MUTED: ParagraphStyle) -> Table:
    # Build 4 “cards” as 4 columns, 2 rows:
    # row 1 = labels, row 2 = values
    labels = ["Total Rx", "Total Cost", "Payer Paid", "Coverage"]

    values = [
        f"{int(kpis.get('total_rx', 0)):,}",
        _money(kpis.get("total_cost", 0.0)),
        _money(kpis.get("payer_paid", 0.0)),
        f"{float(kpis.get('coverage_pct', 0.0)):.1f}%",
    ]

    data = [
        [Paragraph(f"<b>{lab}</b>", MUTED) for lab in labels],
        [Paragraph(f"<b>{val}</b>", BODY) for val in values],
    ]

    col_w = (letter[0] - 72) / 4  # page width - margins
    t = Table(data, colWidths=[col_w] * 4)

    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), THEME["card"]),
                ("BOX", (0, 0), (-1, -1), 0.6, THEME["table_grid"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, THEME["table_grid"]),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _df_to_table(df: pd.DataFrame, max_rows: int = 16) -> Table:
    df2 = df.copy().head(max_rows)

    money_cols = {"TOTAL_COST", "PAYER_PAID", "PATIENT_PAID", "TOTAL_OOP"}
    pct_cols = {"COVERAGE_PCT"}

    for c in df2.columns:
        if c in money_cols:
            df2[c] = df2[c].apply(_money)
        elif c in pct_cols:
            df2[c] = df2[c].apply(_pct)

    data = [list(df2.columns)] + df2.values.tolist()

    tbl = Table(data, repeatRows=1, colWidths=None)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), THEME["table_header"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), THEME["text"]),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.35, THEME["table_grid"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFBFD")]),
            ]
        )
    )
    return tbl


def _render_narrative(narrative: str, H2, BODY, BULLET):
    """
    Makes the narrative look like a report:
    - Heading lines become H2
    - Bullet lines become bullets
    - Other lines become BODY
    """
    elems = []
    lines = [ln.rstrip() for ln in narrative.splitlines() if ln.strip()]

    for ln in lines:
        # section heading heuristics
        if ln.strip().endswith(":") or ln.strip().startswith(("1)", "2)", "3)", "4)", "5)")):
            elems.append(Paragraph(ln.strip(), H2))
            continue

        # bullet heuristics
        if ln.strip().startswith(("-", "•")):
            text = ln.strip().lstrip("-•").strip()
            elems.append(Paragraph(text, BULLET, bulletText="•"))
            continue

        elems.append(Paragraph(ln.strip(), BODY))

    return elems


# =========================================================
# LangGraph workflow
# =========================================================
class ReportState(TypedDict, total=False):
    payload: Dict[str, Any]
    report_type: str
    api_key: str
    model: str
    temperature: float
    narrative: str


def node_generate_narrative(state: ReportState) -> ReportState:
    user_prompt = _user_prompt(state["report_type"], state["payload"])
    narrative = call_openai_text(
        api_key=state["api_key"],
        model=state["model"],
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=state.get("temperature", 0.2),
    )
    state["narrative"] = narrative
    return state


def build_graph():
    graph = StateGraph(ReportState)
    graph.add_node("generate_narrative", node_generate_narrative)
    graph.set_entry_point("generate_narrative")
    graph.add_edge("generate_narrative", END)
    return graph.compile()


def run_report_graph(payload: Dict[str, Any], report_type: str, api_key: str, model: str, temperature: float = 0.2) -> str:
    app = build_graph()
    out = app.invoke(
        {
            "payload": payload,
            "report_type": report_type,
            "api_key": api_key,
            "model": model,
            "temperature": temperature,
        }
    )
    return out.get("narrative", "")


# =========================================================
# Main: generate PDF
# =========================================================
def generate_ai_pdf_report(
    meta: Dict[str, Any],
    kpis: Dict[str, Any],
    payer_agg: pd.DataFrame,
    med_oop: pd.DataFrame,
    review_tbl: pd.DataFrame,
    fig_split,
    fig_cov,
    fig_oop,
    api_key: str,
    model: str,
    temperature: float = 0.2,
    max_review_rows_for_llm: int | None = None,  # None => all rows
) -> str:
    H1, H2, BODY, MUTED, BULLET = _build_styles()

    report_type = meta.get("report_type", "Leadership (Executive TL;DR)")

    payload = pack_payload(
        meta=meta,
        kpis=kpis,
        payer_agg=payer_agg,
        med_oop=med_oop,
        review_tbl=review_tbl,
        max_review_rows=max_review_rows_for_llm,
    )

    narrative = run_report_graph(
        payload=payload,
        report_type=report_type,
        api_key=api_key,
        model=model,
        temperature=temperature,
    )

    # Apply plot aesthetics BEFORE export
    fig_split = _apply_plotly_style(fig_split, "Payer vs Patient Payment Split")
    fig_cov = _apply_plotly_style(fig_cov, "Medication Coverage Rate by Payer")
    fig_oop = _apply_plotly_style(fig_oop, "Top Medications by Patient Out-of-Pocket Cost")

    # Export figures to PNGs
    tmpdir = tempfile.mkdtemp(prefix="medcov_report_")
    split_png = os.path.join(tmpdir, "split.png")
    cov_png = os.path.join(tmpdir, "cov.png")
    oop_png = os.path.join(tmpdir, "oop.png")

    with open(split_png, "wb") as f:
        f.write(_fig_to_png_bytes(fig_split))
    with open(cov_png, "wb") as f:
        f.write(_fig_to_png_bytes(fig_cov))
    with open(oop_png, "wb") as f:
        f.write(_fig_to_png_bytes(fig_oop))

    # PDF output path
    pdf_path = os.path.join(tmpdir, "Medication_Coverage_AI_Report.pdf")
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=70,     # leave space for header bar
        bottomMargin=36,
        title="Medication Coverage AI Report",
    )

    elems = []

    # --------------------
    # Page 1
    # --------------------
    elems.append(Paragraph("2-Page Report", H1))
    elems.append(Paragraph(f"<b>Payers Reviewed:</b> {', '.join(meta.get('selected_payers', [])) or 'None selected'}", MUTED))
    elems.append(Spacer(1, 10))

    elems.append(_kpi_cards(kpis, BODY, MUTED))
    elems.append(Spacer(1, 12))

    elems.append(Paragraph("Key Charts", H2))
    elems.append(Paragraph("Payer vs Patient Payment Split", BODY))
    elems.append(Spacer(1, 6))
    elems.append(RLImage(split_png, width=7.0 * inch, height=2.7 * inch))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Coverage Rate by Payer", BODY))
    elems.append(Spacer(1, 6))
    elems.append(RLImage(cov_png, width=7.0 * inch, height=2.7 * inch))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Narrative Summary", H2))
    elems.extend(_render_narrative(narrative, H2, BODY, BULLET))

    elems.append(PageBreak())

    # --------------------
    # Page 2
    # --------------------
    elems.append(Paragraph("Drilldown", H1))
    elems.append(Paragraph("Top out-of-pocket drivers + payer-medication coverage review.", MUTED))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Top Medications by Patient Out-of-Pocket Cost", H2))
    elems.append(Spacer(1, 6))
    elems.append(RLImage(oop_png, width=7.0 * inch, height=3.0 * inch))
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Payer–Medication Coverage Review (Top Meds)", H2))
    display_cols = [
        "PAYER_NAME",
        "MEDICATION_CODE",
        "MEDICATION_NAME",
        "PRESCRIPTIONS",
        "TOTAL_COST",
        "PAYER_PAID",
        "PATIENT_PAID",
        "COVERAGE_PCT",
    ]
    tbl = _df_to_table(review_tbl[[c for c in display_cols if c in review_tbl.columns]], max_rows=16)
    elems.append(tbl)
    elems.append(Spacer(1, 10))

    elems.append(Paragraph("Notes", H2))
    elems.append(
        Paragraph(
            "This report is generated from dashboard aggregates for the selected date range and payers. "
            "For deeper analysis, drill into patient-level encounters and plan-level formulary/prior-auth rules.",
            BODY,
        )
    )

    # Build with header/footer
    doc.build(
        elems,
        onFirstPage=lambda c, d: _draw_header_footer(c, d, meta),
        onLaterPages=lambda c, d: _draw_header_footer(c, d, meta),
    )

    return pdf_path