
import streamlit as st
import pandas as pd
from Connect import run_query
from datetime import date
import plotly.express as px

st.set_page_config(
    page_title="Audit Dashboard",
    layout="wide",
)

# --------- TITLE ---------
st.markdown(
    "<h1 style='text-align:center; margin-top: -60px;'>📊 Health System Claims & Revenue Analytics</h1>",
    unsafe_allow_html=True,
)

PAYER_COLOR_MAP = {
    "Medicare": "#438CF3",        
    "Medicaid": "#A2F2FC",        
    "Blue Cross Blue Shield": "#35B76B",  
    "Dual Eligible": "#F28B82",   
    "Humana": "#8A6FD1",          
}

# ======================================================================
# Sidebar: global date filters + payer filters
# ======================================================================

# Global date bounds from CLAIMS_AUDIT
date_bounds_query = """
    SELECT 
        MIN(FIRST_TRANSACTION_DATE) AS MIN_DATE,
        MAX(FIRST_TRANSACTION_DATE) AS MAX_DATE
    FROM PUBLIC.CLAIMS_AUDIT;
"""
bounds_df = run_query(date_bounds_query)

min_date = pd.to_datetime(bounds_df["MIN_DATE"][0]).date()
max_date = (
    pd.to_datetime(bounds_df["MIN_DATE"][0]).date()
    if pd.isna(bounds_df["MAX_DATE"][0])
    else pd.to_datetime(bounds_df["MAX_DATE"][0]).date()
)

# Initialize session state for filters on first run
if "start_date" not in st.session_state:
    st.session_state["start_date"] = min_date
if "end_date" not in st.session_state:
    st.session_state["end_date"] = max_date

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

    st.write("")  # spacing
    st.sidebar.markdown("### Payers to include")
    # Payer selection (limited to 5)
    payer_filter_names = [
        "Medicare",
        "Medicaid",
        "Blue Cross Blue Shield",
        "Dual Eligible",
        "Humana",
    ]
    # selected_payers = st.multiselect(
    #     "Payers to include",
    #     options=payer_filter_names,
    #     default=payer_filter_names,
    # )
    selected_payers = [
    payer for payer in payer_filter_names
    if st.sidebar.checkbox(payer, value=True)
    ]   

    st.write("")

    if st.button("🔄 Apply filters & refresh"):
        st.session_state["start_date"] = proposed_start
        st.session_state["end_date"] = proposed_end
        st.rerun()

start_date = st.session_state["start_date"]
end_date = st.session_state["end_date"]

if not selected_payers:
    st.warning("Please select at least one payer to see results.")
    st.stop()

# ======================================================================
# Main: KPIs using CLAIMS_AUDIT (filtered by payer)
# ======================================================================

st.markdown(
    "<h3 style='text-align:center;'>Claims & Revenue Audit Overview</h3>",
    unsafe_allow_html=True
)

# 1) Pull filtered data from CLAIMS_AUDIT
main_query = f"""
    SELECT
        CLAIM_ID,
        PATIENT_ID,
        PROVIDER_ID,
        SUPERVISING_PROVIDER_ID,
        PAYER_ID,
        DEPARTMENT_ID,
        APPOINTMENT_ID,
        SERVICE_DATE,
        FIRST_TRANSACTION_DATE,
        LAST_TRANSACTION_DATE,
        SETTLEMENT_DAYS,
        CLAIM_STATUS,
        CLAIM_TYPE_ID,
        PRIMARY_DIAGNOSIS,
        TOTAL_OUTSTANDING,
        TOTAL_CHARGES,
        TOTAL_PAYMENTS,
        TOTAL_ADJUSTMENTS,
        TOTAL_TRANSFERS_IN,
        TOTAL_TRANSFERS_OUT,
        NET_VARIANCE,
        CLAIM_EXCEPTION_CATEGORY
    FROM PUBLIC.CLAIMS_AUDIT
    WHERE FIRST_TRANSACTION_DATE BETWEEN '{start_date}' AND '{end_date}'
"""
df = run_query(main_query)

if df.empty:
    st.warning("No data for the selected date range.")
    st.stop()

# Bring in payer names once and filter by selected payers
payer_dim = run_query(
    """
    SELECT PAYER_ID, PAYER_NAME
    FROM PUBLIC.DIM_PAYERS
    """
)
payer_dim["PAYER_ID"] = payer_dim["PAYER_ID"].astype(str)
df["PAYER_ID"] = df["PAYER_ID"].astype(str)

df = df.merge(payer_dim, on="PAYER_ID", how="left")
df["PAYER_NAME"] = df["PAYER_NAME"].fillna("Other / Unknown")

# Filter to chosen payer names
df = df[df["PAYER_NAME"].isin(selected_payers)]

if df.empty:
    st.warning("No data for the selected payer(s) and date range.")
    st.stop()

# Ensure datetime
df["FIRST_TRANSACTION_DATE"] = pd.to_datetime(df["FIRST_TRANSACTION_DATE"])

# ---------------- KPIs (on filtered payers) ----------------
total_charges = float(pd.to_numeric(df["TOTAL_CHARGES"], errors="coerce").sum())
total_payments = float(pd.to_numeric(df["TOTAL_PAYMENTS"], errors="coerce").sum())
net_variance = float(pd.to_numeric(df["NET_VARIANCE"], errors="coerce").sum())
total_claims = int(df["CLAIM_ID"].nunique())

# Underpayment rate
underpaid_claims = (df["CLAIM_EXCEPTION_CATEGORY"] == "UNDERPAID").sum()
underpayment_rate = (
    underpaid_claims / total_claims * 100 if total_claims > 0 else 0
)

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(
        f"""
        <div style="text-align:center;">
            <div style="font-size:22px; font-weight:600;">Total Charges</div>
            <div style="font-size:22px; color:gray;">${total_charges:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with k2:
    st.markdown(
        f"""
        <div style="text-align:center;">
            <div style="font-size:22px; font-weight:600;">Total Payments</div>
            <div style="font-size:22px; color:gray;">${total_payments:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with k3:
    st.markdown(
        f"""
        <div style="text-align:center;">
            <div style="font-size:22px; font-weight:600;">Net Variance</div>
            <div style="font-size:22px; color:gray;">${net_variance:,.2f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with k4:
    st.markdown(
        f"""
        <div style="text-align:center;">
            <div style="font-size:22px; font-weight:600;">Underpayment Rate</div>
            <div style="font-size:22px; color:gray;">{underpayment_rate:.1f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# ==================================================================
# Audit visuals – based on CLAIMS_AUDIT + DIM_PAYERS
# ==================================================================

audit_query = f"""
    SELECT
        CLAIM_ID,
        SERVICE_DATE,
        PAYER_ID,
        TOTAL_CHARGES,
        TOTAL_PAYMENTS,
        NET_VARIANCE
    FROM PUBLIC.CLAIMS_AUDIT
    WHERE SERVICE_DATE BETWEEN '{start_date}' AND '{end_date}'
"""
df_audit = run_query(audit_query)

if df_audit.empty:
    st.warning("No audit data for the selected date range.")
    st.stop()

# Join payer names and filter by selected payers
df_audit["PAYER_ID"] = df_audit["PAYER_ID"].astype(str)
df_audit = df_audit.merge(payer_dim, on="PAYER_ID", how="left")
df_audit["PAYER_NAME"] = df_audit["PAYER_NAME"].fillna("Other / Unknown")
df_audit = df_audit[df_audit["PAYER_NAME"].isin(selected_payers)]

if df_audit.empty:
    st.warning("No audit data for the selected payer(s) and date range.")
    st.stop()

# Ensure date type & numeric
df_audit["SERVICE_DATE"] = pd.to_datetime(df_audit["SERVICE_DATE"])
for col in ["TOTAL_CHARGES", "TOTAL_PAYMENTS", "NET_VARIANCE"]:
    df_audit[col] = pd.to_numeric(df_audit[col], errors="coerce")



# ------------------------------------------------------------------
# 1) Payments over time (monthly) – one line per payer
# ------------------------------------------------------------------
df_month = (
    df_audit
    .groupby([pd.Grouper(key="SERVICE_DATE", freq="ME"), "PAYER_NAME"])
    .agg({
        "TOTAL_PAYMENTS": "sum"
    })
    .reset_index()
)
df_month["MONTH"] = df_month["SERVICE_DATE"].dt.to_period("M").astype(str)

c1, c2 = st.columns(2)

with c1:
    fig_trend = px.line(
        df_month,
        x="MONTH",
        y="TOTAL_PAYMENTS",
        color="PAYER_NAME",
        markers=True,
        title="Payments Over Time by Payer",
        color_discrete_map=PAYER_COLOR_MAP
    )
    fig_trend.update_layout(
        xaxis_title="Month",
        yaxis_title="Total Payments",
        legend_title="Payer"
    )
    st.plotly_chart(fig_trend, width='stretch')

# ------------------------------------------------------------------
# 2) Top payers by total variance (filtered set)
# ------------------------------------------------------------------
df_payer_var = (
    df_audit
    .groupby(["PAYER_ID", "PAYER_NAME"], as_index=False)
    .agg({
        "TOTAL_CHARGES": "sum",
        "TOTAL_PAYMENTS": "sum",
        "NET_VARIANCE": "sum"
    })
)

df_payer_var["ABS_VARIANCE"] = df_payer_var["NET_VARIANCE"].abs()
df_payer_top = (
    df_payer_var
    .sort_values("ABS_VARIANCE", ascending=False)
    .head(10)
)

with c2:
    fig_payer_var = px.bar(
        df_payer_top,
        x="PAYER_NAME",
        y="NET_VARIANCE",
        title="Top Payers by Payment Variance",
        color="PAYER_NAME",
        color_discrete_map=PAYER_COLOR_MAP
    )
    fig_payer_var.update_layout(
        xaxis_title="Payer",
        yaxis_title="Total Variance (Payments - Charges)",
        xaxis_tickangle=-35,
        showlegend=False,
    )
    st.plotly_chart(fig_payer_var, width='stretch')



r1, r2 = st.columns(2)


# ------------------------------------------------------------------
# 3) Payer variance vs charges (contract review scatter) – colored by payer
# ------------------------------------------------------------------
df_payer_scatter = (
    df_audit
    .groupby(["PAYER_ID", "PAYER_NAME"], as_index=False)
    .agg({
        "CLAIM_ID": "nunique",
        "TOTAL_CHARGES": "sum",
        "NET_VARIANCE": "sum"
    })
    .rename(columns={
        "CLAIM_ID": "TOTAL_CLAIMS"
    })
)

with r1:
    fig_scatter = px.scatter(
        df_payer_scatter,
        x="TOTAL_CHARGES",
        y="NET_VARIANCE",
        size="TOTAL_CLAIMS",
        hover_name="PAYER_NAME",
        color="PAYER_NAME",
        title="Payer Variance vs Total Charges",
        color_discrete_map=PAYER_COLOR_MAP
    )
    fig_scatter.update_layout(
        xaxis_title="Total Charges",
        yaxis_title="Total Variance (Payments - Charges)",
        legend_title="Payer"
    )
    st.plotly_chart(fig_scatter, width='stretch')



# ------------------------------------------------------------------
# 4) Distribution of variance per claim
# ------------------------------------------------------------------


df_payer_decision = (
    df_audit
    .groupby(["PAYER_ID", "PAYER_NAME"], as_index=False)
    .agg({
        "CLAIM_ID": "nunique",
        "TOTAL_CHARGES": "sum",
        "TOTAL_PAYMENTS": "sum",
        "NET_VARIANCE": "sum"
    })
    .rename(columns={
        "CLAIM_ID": "TOTAL_CLAIMS"
    })
)

# Calculate variance %
df_payer_decision["VARIANCE_PCT"] = (
    df_payer_decision["NET_VARIANCE"] / df_payer_decision["TOTAL_CHARGES"] * 100
).round(3)

# Risk Labels
def risk_label(pct):
    if pct >= 1.0:
        return "🟢 Strong"
    elif pct >= 0.2:
        return "🟡 Stable"
    else:
        return "🔴 Weak"

# Business Recommendation
def recommendation(pct):
    if pct >= 1.0:
        return "Favorable contract – No action needed"
    elif pct >= 0.2:
        return "Monitor – Review during next renewal"
    else:
        return "Low margin – Prioritize renegotiation"

df_payer_decision["RISK_LEVEL"] = df_payer_decision["VARIANCE_PCT"].apply(risk_label)
df_payer_decision["CONTRACT_ACTION"] = df_payer_decision["VARIANCE_PCT"].apply(recommendation)

df_dashboard = df_payer_decision[["PAYER_NAME", "TOTAL_CLAIMS", "TOTAL_CHARGES", "TOTAL_PAYMENTS", "NET_VARIANCE", "VARIANCE_PCT", "RISK_LEVEL", "CONTRACT_ACTION"]].copy()

with r2:
    st.markdown("<br><br><br><br>", unsafe_allow_html=True)

    st.dataframe(
    df_dashboard.sort_values("NET_VARIANCE", ascending=False),
    height=230,
    width='stretch'
    )

