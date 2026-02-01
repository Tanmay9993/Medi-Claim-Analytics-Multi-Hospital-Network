# # =========================================================
# # File: Medication_Coverage_Dashboard.py
# # =========================================================


import os
import streamlit as st
import pandas as pd
import plotly.express as px
from Connect import run_query
from AI_Report_Generator import generate_ai_pdf_report

# =========================================================
# Page config
# =========================================================
st.set_page_config(
    page_title="Medication Coverage Analytics",
    layout="wide",
)


st.markdown(
    """
    <h1 style="
        text-align:center; 
        margin-top:-60px;   /* pull closer to top */
        margin-bottom: -60px; /* reduce gap under title */
    ">
        💊 Medication Coverage & Payer Analytics
    </h1>
    """,
    unsafe_allow_html=True,
)

def enlarge_plot_fonts(fig):
    fig.update_layout(
        title_font=dict(size=22),
        font=dict(size=20),
        legend=dict(font=dict(size=20)),
        margin=dict(l=60, r=40, t=40, b=20),
    )

    fig.update_xaxes(
        title_font=dict(size=22),
        tickfont=dict(size=20),
    )

    fig.update_yaxes(
        title_font=dict(size=22),
        tickfont=dict(size=20),
    )

    return fig


# =========================================================
# Payer Color Map (shared with report)
# =========================================================
PAYER_COLOR_MAP = {
    "Medicare": "#438CF3",
    "Medicaid": "#A2F2FC",
    "Blue Cross Blue Shield": "#35B76B",
    "Dual Eligible": "#F28B82",
    "Humana": "#8A6FD1",
    "Other / Unknown": "#9CA3AF",  # fallback
}

# =========================================================
# Sidebar filters: date bounds
# =========================================================

st.markdown(
    """
    <style>
    /* Sidebar container */
    section[data-testid="stSidebar"] {
        font-size: 22px;
    }

    /* Sidebar labels */
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] div {
        font-size: 22px !important;
    }

    /* Sidebar headers */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 22px !important;
        font-weight: 600;
    }
    
    /* Date input text */
    section[data-testid="stSidebar"] input[type="text"] {
        font-size: 20px !important;
        padding: 4px 6px !important;
    }

    /* Buttons */
    section[data-testid="stSidebar"] button {
        font-size: 22px !important;
        padding: 8px 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    /* Scrollable wrapper */
    .big-table-container {
        max-height: 350px;
        overflow-y: auto;
        overflow-x: auto;
        border: 1px solid #e5e7eb;
    }

    /* Actual table */
    .big-table-container table {
        width: 100%;
        border-collapse: collapse;
        font-size: 20px;
    }

    .big-table-container th {
        font-size: 20px;
        font-weight: 600;
        padding: 6px 10px;
        background-color: #f3f4f6;
        text-align: left;
        position: sticky;   
        top: 0;
        z-index: 2;
    }

    .big-table-container td {
        font-size: 20px;
        padding: 6px 10px;
    }

    .big-table-container table,
    .big-table-container th,
    .big-table-container td {
        border: 1px solid #e5e7eb;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
    /* Force large font for download button */
    div[data-testid="stDownloadButton"] button {
        font-size: 22px !important;
        font-weight: 600 !important;
        padding: 10px 18px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

date_bounds_query = """
    SELECT 
        MIN(MED_START_TS) AS MIN_DATE,
        MAX(MED_START_TS) AS MAX_DATE
    FROM PUBLIC.FACT_MEDICATIONS
"""
bounds_df = run_query(date_bounds_query)

min_date = pd.to_datetime(bounds_df["MIN_DATE"][0]).date()
max_date = pd.to_datetime(bounds_df["MAX_DATE"][0]).date()

# Initialize session state once
if "start_date" not in st.session_state:
    st.session_state["start_date"] = min_date
if "end_date" not in st.session_state:
    st.session_state["end_date"] = max_date

# =========================
# AI report session state
# =========================
if "last_report_path" not in st.session_state:
    st.session_state["last_report_path"] = None

# =========================================================
# Sidebar UI
# =========================================================
with st.sidebar:
    st.header("Filters")

    st.caption("Start date")
    proposed_start = st.date_input(
        "Start",
        value=st.session_state["start_date"],
        min_value=min_date,
        max_value=max_date,
    )

    st.caption("End date")
    proposed_end = st.date_input(
        "End",
        value=st.session_state["end_date"],
        min_value=min_date,
        max_value=max_date,
    )

    st.write("")
    if st.button("🔄 Apply filters & refresh"):
        st.session_state["start_date"] = proposed_start
        st.session_state["end_date"] = proposed_end
        st.rerun()

    st.markdown("### Payers")
    payer_filter_names = [
        "Medicaid",
        "Medicare",
        "Blue Cross Blue Shield",
        "Dual Eligible",
    ]

    selected_payers = []
    for p in payer_filter_names:
        # unique keys so Streamlit doesn't confuse state across reruns
        if st.checkbox(p, value=True, key=f"payer_checkbox_{p}"):
            selected_payers.append(p)

    if not selected_payers:
        st.warning("Please select at least one payer to see results.")
        st.stop()



    # -------------------------
    # AI Control Panel (single report type)
    # -------------------------
    st.markdown("---")
    st.subheader("AI Report Generator")

    st.markdown(
        "<p style='font-size:14px;'>Report Type: <b>Medication Coverage Summary</b></p>",
        unsafe_allow_html=True,
    )
    report_type = "Medication Coverage Summary"

    generate_report_clicked = st.button("📄 Generate AI PDF Report", type="primary")

start_date = st.session_state["start_date"]
end_date = st.session_state["end_date"]

# =========================================================
# Main data pull
# =========================================================
main_query = f"""
    SELECT
        PATIENT_ID,
        PAYER_ID,
        ENCOUNTER_ID,
        MED_START_TS,
        MEDICATION_CODE,
        MEDICATION_NAME,
        BASE_COST,
        PAYER_COVERAGE,
        TOTAL_COST,
        DISPENSES
    FROM PUBLIC.FACT_MEDICATIONS
    WHERE MED_START_TS::DATE BETWEEN '{start_date}' AND '{end_date}'
"""
df = run_query(main_query)

if df.empty:
    st.warning("No data for selected date range.")
    st.stop()


# Pull payer dimension and join names
payer_dim = run_query("SELECT PAYER_ID, PAYER_NAME FROM PUBLIC.DIM_PAYERS")
df["PAYER_ID"] = df["PAYER_ID"].astype(str)
payer_dim["PAYER_ID"] = payer_dim["PAYER_ID"].astype(str)

df = df.merge(payer_dim, on="PAYER_ID", how="left")

# Normalize payer name and apply payer filter once
df["PAYER_NAME"] = df["PAYER_NAME"].fillna("Other / Unknown").astype(str).str.strip()
df = df[df["PAYER_NAME"].isin(selected_payers)].copy()

if df.empty:
    st.warning("No data after applying filters.")
    st.stop()

# Ensure numeric
for col in ["BASE_COST", "PAYER_COVERAGE", "TOTAL_COST", "DISPENSES"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

df["OUT_OF_POCKET"] = df["TOTAL_COST"] - df["PAYER_COVERAGE"]



# =========================================================
# KPIs
# =========================================================
total_rx = int(df.shape[0])
total_cost = float(df["TOTAL_COST"].sum())
payer_paid = float(df["PAYER_COVERAGE"].sum())
patient_paid = float(df["OUT_OF_POCKET"].sum())
coverage_pct = (payer_paid / total_cost * 100) if total_cost > 0 else 0.0

k1, k2, k3, k4 = st.columns(4)

def centered_metric(col, label, value):
    col.markdown(
        f"""
        <div style="text-align:center;">
            <div style="font-size:28px; color:#6c757d; font-weight:600;">
                {label}
            </div>
            <div style="font-size:32px; font-weight:700; margin-top:4px;">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

centered_metric(k1, "Total Prescriptions", f"{total_rx:,}")
centered_metric(k2, "Total Medication Cost", f"${total_cost:,.2f}")
centered_metric(k3, "Payer Paid", f"${payer_paid:,.2f}")
centered_metric(k4, "Coverage Rate", f"{coverage_pct:.1f}%")

# thinner separator with less vertical space
st.markdown(
    """
    <div style="
        height:1px;
        background-color:#e5e7eb;
        margin-top:-4px;
        margin-bottom:8px;
    "></div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Visual 1: Payer vs Patient Split
# =========================================================
c1, c2 = st.columns(2)

with c1:
    pay_split = pd.DataFrame(
        {"Type": ["Payer Paid", "Patient Paid"], "Amount": [payer_paid, patient_paid]}
    )
    fig_split = px.pie(
    pay_split,
    names="Type",
    values="Amount",
    title="Payer vs Patient Payment Split",
    hole=0.45,
    color="Type",
    color_discrete_map={
        "Payer Paid": "#4CF3C1",     # Blue
        "Patient Paid": "#FF9B49",   # Soft red (out-of-pocket pain)
        },
    )
    fig_split.update_layout(
        font=dict(size=16),
        legend=dict(font=dict(size=12)),
        title_font=dict(size=18),
    )
    fig_split = enlarge_plot_fonts(fig_split)
    st.plotly_chart(fig_split, width="stretch")

# =========================================================
# Visual 2: Coverage rate by payer (with custom colors + larger font)
# =========================================================
with c2:
    payer_agg = (
        df.groupby("PAYER_NAME", as_index=False)
        .agg(
            TOTAL_COST=("TOTAL_COST", "sum"),
            PAYER_COVERAGE=("PAYER_COVERAGE", "sum"),
        )
    )

    payer_agg["COVERAGE_PCT"] = (
        (payer_agg["PAYER_COVERAGE"] / payer_agg["TOTAL_COST"]) * 100
    ).replace([float("inf"), -float("inf")], 0).fillna(0)

    unique_payers = payer_agg["PAYER_NAME"].unique().tolist()
    color_map = {
        p: PAYER_COLOR_MAP.get(p, PAYER_COLOR_MAP["Other / Unknown"])
        for p in unique_payers
    }

    fig_cov = px.bar(
        payer_agg.sort_values("COVERAGE_PCT"),
        x="PAYER_NAME",
        y="COVERAGE_PCT",
        color="PAYER_NAME",
        color_discrete_map=color_map,
        title="Medication Coverage Rate by Payer",
        labels={"COVERAGE_PCT": "Coverage %", "PAYER_NAME": "Payer"},
    )
    fig_cov.update_layout(
        xaxis_tickangle=-30,
        showlegend=False,
        font=dict(size=16),
        title_font=dict(size=18),
    )
    fig_cov = enlarge_plot_fonts(fig_cov)
    st.plotly_chart(fig_cov, width="stretch")

# =========================================================
# Visual 3: Top medications by patient out-of-pocket
# =========================================================
med_oop = (
    df.groupby(["MEDICATION_CODE", "MEDICATION_NAME"], as_index=False)
    .agg(
        TOTAL_OOP=("OUT_OF_POCKET", "sum"),
        TOTAL_RX=("DISPENSES", "sum"),
    )
    .sort_values("TOTAL_OOP", ascending=False)
    .head(10)
)

med_oop["MED_CODE_STR"] = med_oop["MEDICATION_CODE"].astype(str).str.strip()
med_code_order = med_oop["MED_CODE_STR"].tolist()

fig_oop = px.bar(
    med_oop,
    x="MED_CODE_STR",
    y="TOTAL_OOP",
    title="Top Medications by Patient Out-of-Pocket Cost",
    labels={"TOTAL_OOP": "Out-of-Pocket ($)", "MED_CODE_STR": "Medication Code"},
    category_orders={"MED_CODE_STR": med_code_order},
)
fig_oop.update_traces(marker_color="#8653F4") 
fig_oop.update_xaxes(type="category", tickformat=None)
fig_oop.update_layout(
    xaxis_tickangle=-35,
    font=dict(size=16),
    title_font=dict(size=18),
)
fig_oop = enlarge_plot_fonts(fig_oop)
st.plotly_chart(fig_oop, width="stretch")


# =========================================================
# Visual 4: Payer–Medication Coverage Review (Top Meds)
# =========================================================



review_tbl = (
    df.groupby(["PAYER_NAME", "MEDICATION_CODE", "MEDICATION_NAME"], as_index=False)
    .agg(
        PRESCRIPTIONS=("DISPENSES", "sum"),
        TOTAL_COST=("TOTAL_COST", "sum"),
        PAYER_PAID=("PAYER_COVERAGE", "sum"),
        PATIENT_PAID=("OUT_OF_POCKET", "sum"),
    )
)

review_tbl["COVERAGE_PCT"] = (
    (review_tbl["PAYER_PAID"] / review_tbl["TOTAL_COST"]) * 100
).replace([float("inf"), -float("inf")], 0).fillna(0).round(2)

# Filter to only the top meds from Visual 3
top_med_df = med_oop[["MEDICATION_NAME", "MEDICATION_CODE"]].copy()
review_tbl = review_tbl.merge(top_med_df, on=["MEDICATION_NAME", "MEDICATION_CODE"], how="inner")

# Enforce ordering to match Visual 3 (by medication code order)
review_tbl["MED_CODE_STR"] = review_tbl["MEDICATION_CODE"].astype(str).str.strip()
review_tbl["MED_CODE_ORDER"] = pd.Categorical(
    review_tbl["MED_CODE_STR"], categories=med_code_order, ordered=True
)

review_tbl = (
    review_tbl.sort_values(["MED_CODE_ORDER", "TOTAL_COST"], ascending=[True, False])
    .drop(columns=["MED_CODE_STR", "MED_CODE_ORDER"])
)

st.markdown("### Payer–Medication Coverage Review (Top Meds from OOP Chart)")

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

tbl_df = review_tbl[display_cols].copy()

# simple formatting for money & percentage
for col in ["TOTAL_COST", "PAYER_PAID", "PATIENT_PAID"]:
    tbl_df[col] = tbl_df[col].apply(lambda x: f"${float(x):,.2f}")
tbl_df["COVERAGE_PCT"] = tbl_df["COVERAGE_PCT"].apply(lambda x: f"{float(x):.2f}%")

table_html = tbl_df.to_html(index=False)
st.markdown(
    f'<div class="big-table-container">{table_html}</div>',
    unsafe_allow_html=True,
)


# =========================================================
# AI Report Generation (messages + download in sidebar)
# =========================================================
if generate_report_clicked:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        # Show error specifically in sidebar
        with st.sidebar:
            st.error("OPENAI_API_KEY is not set. Add it to your .env file.")
    else:
        with st.sidebar:
            with st.spinner("Generating AI PDF report..."):
                meta = {
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                    "selected_payers": selected_payers,
                    "report_type": report_type,
                }

                kpis = {
                    "total_rx": total_rx,
                    "total_cost": total_cost,
                    "payer_paid": payer_paid,
                    "patient_paid": patient_paid,
                    "coverage_pct": coverage_pct,
                }

                pdf_path = generate_ai_pdf_report(
                    meta=meta,
                    kpis=kpis,
                    payer_agg=payer_agg,
                    med_oop=med_oop,
                    review_tbl=review_tbl,
                    fig_split=fig_split,
                    fig_cov=fig_cov,
                    fig_oop=fig_oop,
                    api_key=api_key,
                    model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                    temperature=float(os.getenv("AI_TEMPERATURE", "0.2")),
                    max_review_rows_for_llm=len(review_tbl),
                )

                st.session_state["last_report_path"] = pdf_path

            st.success("Report generated.")

# Download button persists after reruns (also in sidebar)
if st.session_state.get("last_report_path"):
    with st.sidebar:
        with open(st.session_state["last_report_path"], "rb") as f:
            st.download_button(
                "⬇️ Download AI PDF Report",
                data=f,
                file_name="Medication_Coverage_AI_Report.pdf",
                mime="application/pdf",
            )
