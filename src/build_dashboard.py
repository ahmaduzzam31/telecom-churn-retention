"""Build the interactive churn dashboard (docs/index.html, served by GitHub Pages)."""
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go

from dashboard_kit import AQUA, BLUE, CRITICAL, INK, INK_2, ORANGE, build_page

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"
TENURE = ["0-6 m", "7-12 m", "13-24 m", "25-48 m", "49-72 m"]

con = duckdb.connect()
for t in ["customers", "subscriptions", "billing", "churn"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv('{DATA / (t + '.csv')}', "
                f"auto_type_candidates=['BIGINT','DOUBLE','VARCHAR'])")
sql = lambda f: con.sql((ROOT / "sql" / f).read_text()).df()

kpi = sql("01_churn_kpis.sql").iloc[0]
heat = sql("02_churn_by_contract_tenure.sql")
fibre = sql("03_internet_service_quality.sql")
pay = sql("04_payment_friction.sql")
surv = sql("07_cohort_survival.sql")
roi = pd.read_csv(ROOT / "reports/retention_strategy_roi.csv", index_col=0)

# Heatmap contract x tenure
hp = heat.pivot(index="contract", columns="tenure_band", values="churn_rate_pct")[TENURE]
hn = heat.pivot(index="contract", columns="tenure_band", values="customers")[TENURE]
f1 = go.Figure(go.Heatmap(z=hp.values, x=TENURE, y=hp.index, customdata=hn.values, zmin=0, zmax=60,
                          colorscale=[[0, "#cde2fb"], [0.4, "#6da7ec"], [0.7, "#256abf"], [1, "#0d366b"]],
                          text=[[f"{v:.0f}%" for v in row] for row in hp.values], texttemplate="%{text}",
                          hovertemplate="%{y}, tenure %{x}<br>Churn %{z:.1f}%<br>%{customdata} customers<extra></extra>",
                          showscale=False))
f1.update_yaxes(autorange="reversed", showgrid=False)

# Retention curve
f2 = go.Figure()
f2.add_scatter(x=surv.month, y=surv.month_to_month_pct, name="Month-to-month", mode="lines+markers",
               line=dict(color=ORANGE, width=2.5), marker=dict(size=8))
f2.add_scatter(x=surv.month, y=surv.term_contract_pct, name="1 or 2-year contract", mode="lines+markers",
               line=dict(color=BLUE, width=2.5), marker=dict(size=8))
f2.update_traces(hovertemplate="Month %{x}: %{y:.1f}% still active<extra>%{fullData.name}</extra>")
f2.update_layout(hovermode="x unified", xaxis_title="Months since joining", yaxis_title="% still active")

# Fibre vs DSL with/without tech support
f3 = go.Figure()
for ts, color, name in [("No", CRITICAL, "No tech support"), ("Yes", BLUE, "With tech support")]:
    d = fibre[fibre.tech_support == ts]
    f3.add_bar(x=d.internet_service, y=d.churn_rate_pct, name=name, marker_color=color,
               customdata=d[["customers", "avg_monthly_charge"]],
               hovertemplate="%{x}, " + name + "<br>Churn %{y:.1f}%<br>%{customdata[0]} customers"
               "<br>Avg bill $%{customdata[1]:.2f}<extra></extra>")
f3.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08, yaxis_title="Churn rate (%)")

# Payment method
p = pay.sort_values("churn_rate_pct")
f4 = go.Figure(go.Bar(x=p.churn_rate_pct, y=p.payment_method, orientation="h",
                      marker_color=[CRITICAL if v > 40 else BLUE for v in p.churn_rate_pct],
                      customdata=p[["customers", "vs_avg_pp"]],
                      hovertemplate="%{y}<br>Churn %{x:.1f}% (%{customdata[1]:+.1f}pp vs avg)"
                      "<br>%{customdata[0]} customers<extra></extra>"))
f4.add_vline(x=kpi.churn_rate_pct, line=dict(color=INK_2, width=1, dash="dash"),
             annotation_text="average", annotation_position="top")
f4.update_layout(xaxis_title="Churn rate (%)", bargap=0.35)

# ROI by strategy
r = roi.iloc[::-1]
f5 = go.Figure(go.Bar(x=r.profit / 1000, y=r.index, orientation="h",
                      marker_color=[CRITICAL if v < 0 else (AQUA if n == "Positive expected value" else BLUE)
                                    for n, v in r.profit.items()],
                      customdata=r[["customers contacted", "churners reached", "profit per contact"]],
                      hovertemplate="%{y}<br>Profit $%{x:,.0f}k<br>%{customdata[0]:,} contacted, "
                      "%{customdata[1]:,} churners reached<br>$%{customdata[2]:.2f} per contact<extra></extra>"))
f5.add_vline(x=0, line=dict(color=INK, width=1))
f5.update_layout(xaxis_title="Campaign profit ($ thousands, 12-month margin)", bargap=0.35)

best = roi["profit"].idxmax()
build_page(
    title="Telecom Churn & Retention Dashboard",
    intro="7,043 telecom customers (IBM Telco dataset). Where churn happens, why, and which retention strategy pays. "
          "Hover over any chart for details.",
    kpis=[("Churn rate", f"{kpi.churn_rate_pct:.1f}%", f"{int(kpi.churned_customers):,} of {int(kpi.customers):,} customers"),
          ("Monthly revenue lost", f"${kpi.mrr_lost:,.0f}", f"{kpi.mrr_lost_pct:.1f}% of MRR"),
          ("Early churn (M2M, 0-6 m)", f"{hp.loc['Month-to-month', '0-6 m']:.0f}%", "the danger zone"),
          ("Model ROC AUC", "0.84", "2.9x lift in top decile"),
          ("Best campaign profit", f"${roi.loc[best, 'profit']:,.0f}", "vs loss if contacting everyone")],
    cards=[
        {"title": "Churn rate by contract and tenure", "fig": f1,
         "sub": "Month-to-month customers in their first 6 months churn at 55%."},
        {"title": "Retention curve", "fig": f2, "sub": "Share of customers still active at each tenure milestone."},
        {"title": "Fibre vs DSL, with and without tech support", "fig": f3,
         "sub": "The premium fibre product churns most. Tech support halves it."},
        {"title": "Churn by payment method", "fig": f4, "sub": "Electronic check payers churn at 45%, about 3x automatic payers."},
        {"title": "Retention campaign profit by targeting strategy", "fig": f5, "wide": True, "height": 300,
         "sub": "Model-based targeting turns a loss-making campaign profitable (assumes $60 offer cost, 30% save rate)."},
    ],
    insights=[
        "<b>Lock in new customers early.</b> 55% of month-to-month customers leave within 6 months, against about 10% on 1-year contracts.",
        "<b>Fibre has a service problem.</b> It churns more than DSL at every tenure. Fibre without tech support churns at 49%.",
        "<b>Payment friction matters.</b> Electronic check payers churn at 45%. Moving them to automatic payment is a quick win.",
        "<b>Target, don't blanket.</b> Contacting everyone loses money, while model-based targeting is profitable.",
    ],
    footer="Data: IBM Telco Customer Churn sample dataset. Retention economics are stated assumptions to be validated by A/B test.",
    path=ROOT / "docs/index.html",
)
print("Dashboard written to docs/index.html")
