
# Data Modeling Overview — Financial Audits Dashboard (Snowflake)

## Objective
The goal of this data model is to produce a **single, audit-ready claims fact table** that enables consistent, period-based analysis of insurance payer payment performance.  
The model is designed to support downstream analytics and dashboards without embedding complex business logic in the application layer.

---

## Final Analytics Table
### `PUBLIC.CLAIMS_AUDIT`

This is the **only table consumed by the Streamlit dashboard**.

It represents one row per claim and contains:
- standardized claim and payer identifiers  
- service and transaction timelines  
- aggregated financial outcomes (charges, payments, adjustments)  
- derived audit metrics (net variance, settlement duration)  
- categorical exception flags for payment behavior  

This table is optimized for **payer-level aggregation, comparison across periods, and audit triage**.

---

## Progressive Table Build (Layered Design)

The final audit table is constructed through a small number of well-defined, composable layers.  
Each layer has a single responsibility and adds analytical value.

---

### 1. Claims Context Layer
**Table:** `PUBLIC.CLAIMS_ANALYTICS`  
**Purpose:** Standardize claim-level attributes and payer relationships.

This layer consolidates raw claims data into a clean, analytics-friendly structure by:
- normalizing claim, patient, provider, and department identifiers
- resolving primary and secondary payer identifiers
- standardizing service dates, claim status, and claim type
- consolidating outstanding balances and diagnosis fields

**Why this layer exists**
- Separates clinical and administrative claim context from financial calculations  
- Provides stable payer wiring and service dates required for time-based analysis  
- Prevents downstream analytics from depending on raw, inconsistent source fields  

---

### 2. Financial Transaction Fact Layer
**Table:** `PUBLIC.FACT_CLAIMS_TRANSACTIONS`  
**Purpose:** Store raw financial events at the transaction level.

This table captures:
- charges, payments, adjustments, and transfers
- transaction-level amounts and effective date ranges
- all financial activity associated with a claim

**Why this layer exists**
- Claim financial performance is driven by transaction behavior, not single records  
- Enables accurate rollups and future extensibility (e.g., transaction-level audits)  
- Keeps raw financial data immutable and reusable across models  

---

### 3. Claim Financial Aggregation Layer
**Table:** `PUBLIC.CLAIMS_FINANCIAL_ANALYTICS`  
**Purpose:** Aggregate transaction data into one financial record per claim.

This layer:
- aggregates transactions into claim-level totals (charges, payments, transfers, adjustments)
- derives first and last transaction dates per claim
- aligns claim financials with payer information from the claims context layer

**Why this layer exists**
- Produces consistent, claim-level financial measures
- Enables settlement timing analysis
- Reduces dashboard complexity by precomputing financial aggregates

---

### 4. Audit & Exception Layer (Final)
**Table:** `PUBLIC.CLAIMS_AUDIT`  
**Purpose:** Produce an analytics-ready audit fact table.

This final layer combines claim context and claim financials and adds:
- settlement duration (`SETTLEMENT_DAYS`)
- net payment variance (`TOTAL_PAYMENTS − TOTAL_CHARGES`)
- categorical exception labels (e.g., underpaid, overpaid, zero-pay)

**Why this layer exists**
- Translates raw financial outcomes into **audit-relevant signals**
- Supports rapid payer comparison and prioritization
- Eliminates the need for complex business logic in the dashboard

---

## Dimension Usage
### `PUBLIC.DIM_PAYERS`

A payer dimension table is used to map payer identifiers to human-readable payer names and metadata.  
This table is joined at query time by the dashboard to support filtering, labeling, and interpretation.

---

## Analytical Benefits of This Model

This layered design enables:

- **Consistent payer performance review**
  - uniform definitions of charges, payments, and variance across periods

- **Audit-ready metrics**
  - settlement time and exception flags embedded directly in the fact table

- **Scalable analytics**
  - new dashboards or analyses can reuse the same audit fact without re-deriving logic

- **Clear separation of concerns**
  - raw data ingestion, aggregation, and audit logic are isolated and maintainable

---

## Summary
The data model converts raw claims and financial transactions into a single, governed audit fact table designed for **period-based insurance payer performance analytics**.  
By progressively enriching data through focused layers, the model ensures accuracy, clarity, and reusability for downstream analytical applications.
