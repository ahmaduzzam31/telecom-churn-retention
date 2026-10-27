"""Clean the IBM Telco churn extract and split it into a small star schema for SQL and Power BI.

Outputs (data/processed/)
-------------------------
customers.csv      customer_id, gender, senior_citizen, partner, dependents, tenure_months, tenure_band
subscriptions.csv  customer_id + one column per service, services_count
billing.csv        customer_id, contract, paperless_billing, payment_method, monthly_charges, total_charges
churn.csv          customer_id, churned (0/1)
telco_clean.csv    everything joined (one row per customer) for the notebook
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/telco_customer_churn.csv"
OUT = ROOT / "data/processed"

SERVICES = ["PhoneService", "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
            "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]
ADD_ONS = ["OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies"]


def snake(name: str) -> str:
    fixed = {"customerID": "customer_id", "StreamingTV": "streaming_tv"}
    if name in fixed:
        return fixed[name]
    return "".join("_" + c.lower() if c.isupper() else c for c in name).lstrip("_")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # 11 brand-new customers (tenure 0) have a blank TotalCharges: they have not been billed yet -> 0
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"].str.strip().replace("", np.nan)).fillna(0.0)
    df["SeniorCitizen"] = df["SeniorCitizen"].map({1: "Yes", 0: "No"})
    df["Churn"] = (df["Churn"] == "Yes").astype(int)
    # "No internet service" / "No phone service" mean the same as "No" for analysis
    for col in ["MultipleLines"] + ADD_ONS:
        df[col] = df[col].replace({"No internet service": "No", "No phone service": "No"})
    df["services_count"] = (df[ADD_ONS] == "Yes").sum(axis=1) + (df["PhoneService"] == "Yes") + \
                           (df["InternetService"] != "No")
    df["tenure_band"] = pd.cut(df["tenure"], [-1, 6, 12, 24, 48, 72],
                               labels=["0-6 m", "7-12 m", "13-24 m", "25-48 m", "49-72 m"]).astype(str)
    df.columns = [snake(c) for c in df.columns]
    return df.rename(columns={"tenure": "tenure_months", "churn": "churned"})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = clean(pd.read_csv(RAW))
    df.to_csv(OUT / "telco_clean.csv", index=False)

    cust = ["customer_id", "gender", "senior_citizen", "partner", "dependents", "tenure_months", "tenure_band"]
    subs = ["customer_id"] + [snake(c) for c in SERVICES] + ["services_count"]
    bill = ["customer_id", "contract", "paperless_billing", "payment_method", "monthly_charges", "total_charges"]
    df[cust].to_csv(OUT / "customers.csv", index=False)
    df[subs].to_csv(OUT / "subscriptions.csv", index=False)
    df[bill].to_csv(OUT / "billing.csv", index=False)
    df[["customer_id", "churned"]].to_csv(OUT / "churn.csv", index=False)
    print(f"{len(df):,} customers | churn rate {df.churned.mean():.1%} | columns: {list(df.columns)}")


if __name__ == "__main__":
    main()
