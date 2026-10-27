# Power BI version of the dashboard

The interactive dashboard in [`/docs`](../docs) is built with Python/Plotly so it can be viewed in a browser
without a licence. This folder has everything needed to rebuild it in **Power BI Desktop**.

## 1. Load the data
`Get Data → Text/CSV` and load the four files in `data/processed/`:

| Table | Grain | Key |
|---|---|---|
| `customers` | one row per customer (demographics, tenure, tenure band) | `customer_id` |
| `subscriptions` | services held | `customer_id` |
| `billing` | contract, payment method, charges | `customer_id` |
| `churn` | churn flag (0/1) | `customer_id` |

In Power Query, set `tenure_months`, `monthly_charges`, `total_charges` and `churned` to numeric types.

## 2. Build the model
Model view: relate `customers[customer_id]` **1 → 1** to each of the other three tables (single direction,
from `customers`). Sort `tenure_band` by a helper column (0-6 m = 1 … 49-72 m = 5).

## 3. Add the measures
Create an empty `Measures` table and paste the measures from [`DAX_measures.dax`](DAX_measures.dax).

## 4. Report pages
| Page | Visuals |
|---|---|
| **Overview** | KPI cards (Churn Rate %, MRR Lost, ARPU, Revenue at Risk), churn matrix contract × tenure band with conditional formatting |
| **Drivers** | Bar charts of Churn Rate % by payment method, internet service × tech support, services count. Slicers for contract and senior citizen |
| **Retention targets** | Table of active high-risk customers (`reports/retention_target_list_top500.csv`) with risk score and monthly charge |
