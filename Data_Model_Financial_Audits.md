# Data Modeling Overview — Financial Audits Dashboard (Snowflake)

## Objective
Design a **layered Snowflake data model** that produces a single, audit-ready claims fact table for **period-based insurance payer performance analysis**, while keeping business logic out of the application layer.

---

## Modeling Strategy (High Level)
The model follows a **progressive enrichment approach**:
- Start with **dimensions** for interpretation
- Build **atomic fact tables** for transactions and claims
- Aggregate into **analytics-ready claim facts**
- Finalize into a **dashboard-facing audit table**

---

## 1. Dimension Layer

### `PUBLIC.DIM_PAYERS`
**Role:** Reference dimension  
**Used for:** Interpretation, filtering, labeling

Stores payer identifiers and descriptive attributes.  
Joined only at query or dashboard time to convert payer IDs into readable payer names.

**Why it exists**
- Keeps identifiers separate from analytics logic
- Enables consistent payer naming across all analyses
- Avoids duplicating payer metadata in fact tables

---

## 2. Atomic Fact Layers

### `PUBLIC.FACT_CLAIMS_TRANSACTIONS`
**Role:** Financial transaction fact  
**Grain:** One row per claim transaction

Captures all financial events associated with claims:
- charges, payments, adjustments, transfers
- transaction amounts and effective date ranges

**Why it exists**
- Preserves raw financial behavior at the lowest level
- Enables accurate aggregation and future audit extensions
- Acts as the source of truth for all claim financial calculations

---

### `PUBLIC.CLAIMS_ANALYTICS`
**Role:** Claim context fact  
**Grain:** One row per claim

Standardizes claim-level attributes:
- claim, patient, provider, department identifiers
- primary and secondary payer wiring
- service date, claim status, claim type
- outstanding balances and diagnosis fields

**Why it exists**
- Separates administrative/clinical context from financial logic
- Provides stable payer and service-date references
- Ensures downstream models don’t depend on raw source fields

---

## 3. Aggregated Analytics Layer

### `PUBLIC.CLAIMS_FINANCIAL_ANALYTICS`
**Role:** Claim-level financial aggregates  
**Grain:** One row per claim

Built by aggregating transaction facts and aligning them with claim context.

Adds:
- total charges, payments, transfers, adjustments
- first and last transaction dates per claim
- payer alignment for financial analysis

**Why it exists**
- Converts transaction noise into claim-level financial signals
- Enables settlement timing and period-based filtering
- Simplifies downstream analytics and dashboards

---

## 4. Final Audit & Dashboard Layer

### `PUBLIC.CLAIMS_AUDIT`
**Role:** Audit-ready analytics fact  
**Grain:** One row per claim  
**Dashboard source:** ✅ Yes

This is the **only table consumed by the Streamlit dashboard**.

Enhancements added at this layer:
- settlement duration (`SETTLEMENT_DAYS`)
- net variance (`TOTAL_PAYMENTS − TOTAL_CHARGES`)
- categorical exception flags:
  - UNDERPAID
  - OVERPAID
  - ZERO_PAY
  - NO_CHARGE
  - MATCHED

**Why it exists**
- Translates financial outcomes into audit-relevant signals
- Supports rapid payer comparison and prioritization
- Eliminates business logic from the visualization layer

---

## How This Model Supports Analytics

Because the audit logic is embedded in the warehouse:

- **Payer performance can be reviewed consistently**
  - same definitions across months, quarters, and years

- **Variance becomes actionable**
  - net variance + exception categories enable audit triage

- **Dashboards remain simple**
  - no complex joins or calculations in Streamlit

- **The model scales**
  - additional analytics can reuse the same audit fact table

---

## Summary
This data model progressively transforms raw claims and transaction data into a **single, governed audit fact table** optimized for **period-based insurance payer performance analytics**, ensuring accuracy, maintainability, and decision-ready insights.
