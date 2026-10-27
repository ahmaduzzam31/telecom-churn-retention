# %% [markdown]
# # Telecom Customer Churn & Retention Strategy
#
# **Business question:** 1 in 4 customers left last quarter, taking 30% of monthly recurring revenue with them.
# **Why are customers leaving, who is likely to leave next, and which retention action gives the best return?**
#
# **Data:** [IBM Telco Customer Churn](https://github.com/IBM/telco-customer-churn-on-icp4d) gives 7,043
# customers of a telecom provider with demographics, services, contract, billing and whether they churned.
# Amounts are in the dataset's currency (USD).
#
# **Approach**
# 1. KPIs and revenue at risk (SQL on a 4-table star schema)
# 2. Churn drivers: which factors matter most?
# 3. Customer lifecycle: when do customers leave?
# 4. Deep dive: why does the premium fibre product churn the most?
# 5. Churn prediction model (interpretable and high-accuracy versions)
# 6. Retention targeting: who to contact, and is it profitable?
# 7. A/B test design to prove the retention offer works
# 8. Recommendations

# %%
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
import style  # noqa: E402

style.apply()
FIG = ROOT / "reports/figures"
FIG.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 140)

# ---- Retention economics (illustrative assumptions, change to your company's numbers) ----
OFFER_COST = 60            # cost per contacted customer: e.g. 1 month discount + agent call
SAVE_RATE = 0.30           # share of would-be churners the offer retains
VALUE_HORIZON_MONTHS = 12  # revenue horizon we credit to a saved customer
GROSS_MARGIN = 0.60        # margin on telecom revenue

# %% [markdown]
# ## 1. KPIs and revenue at risk (SQL)
# The raw extract was split into a **star schema**: `customers`, `subscriptions`, `billing`, `churn`.
# That is how the data would sit in a warehouse, and it is the model the Power BI file uses. All queries are in [`/sql`](../sql).

# %%
con = duckdb.connect()
for t in ["customers", "subscriptions", "billing", "churn"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_csv('{ROOT / 'data/processed' / (t + '.csv')}', "
                f"auto_type_candidates=['BIGINT','DOUBLE','VARCHAR'])")
run_sql = lambda name: con.sql((ROOT / "sql" / name).read_text()).df()

kpi = run_sql("01_churn_kpis.sql")
kpi

# %% [markdown]
# **Takeaway:** 26.5% of customers churned, but they took **30.5% of monthly revenue**. Churners pay more than
# average, so churn is a revenue problem, not just a headcount problem.

# %%
df = pd.read_csv(ROOT / "data/processed/telco_clean.csv")
y = df["churned"]

# %% [markdown]
# ## 2. Churn drivers: which factors matter most?
# For every categorical attribute I ran a **chi-square test of independence** against churn and ranked them by
# **Cramér's V** (0 = no association, 1 = perfect). This gives an objective ranking instead of eyeballing charts.

# %%
categorical = ["gender", "senior_citizen", "partner", "dependents", "tenure_band", "phone_service",
               "multiple_lines", "internet_service", "online_security", "online_backup", "device_protection",
               "tech_support", "streaming_tv", "streaming_movies", "contract", "paperless_billing", "payment_method"]

def cramers_v(x, y):
    table = pd.crosstab(x, y)
    chi2, p, *_ = stats.chi2_contingency(table)
    return np.sqrt(chi2 / (table.values.sum() * (min(table.shape) - 1))), p

drivers = pd.DataFrame([(c, *cramers_v(df[c], y)) for c in categorical], columns=["attribute", "cramers_v", "p_value"])
drivers = drivers.sort_values("cramers_v", ascending=False).reset_index(drop=True)
drivers["significant"] = drivers["p_value"] < 0.05
drivers.round(4)

# %%
top_attrs = ["contract", "tenure_band", "internet_service", "payment_method", "online_security", "tech_support"]
labels = {"contract": "Contract", "tenure_band": "Tenure", "internet_service": "Internet service",
          "payment_method": "Payment method", "online_security": "Online security", "tech_support": "Tech support"}
order = {"tenure_band": ["0-6 m", "7-12 m", "13-24 m", "25-48 m", "49-72 m"]}
barh_order = {"tenure_band": order["tenure_band"][::-1]}   # barh draws bottom-up

fig, axes = plt.subplots(2, 3, figsize=(13, 6.5))
for ax, attr in zip(axes.flat, top_attrs):
    rates = df.groupby(attr)["churned"].mean().mul(100)
    rates = rates.reindex(barh_order.get(attr, rates.sort_values().index))
    colors = [style.CRITICAL if r > 40 else style.BLUE for r in rates]
    ax.barh(rates.index, rates.values, color=colors, height=0.6)
    ax.axvline(y.mean() * 100, color=style.INK_2, lw=0.8, ls="--")
    for i, v in enumerate(rates.values):
        ax.text(v + 1, i, f"{v:.0f}%", va="center", fontsize=8.5, color=style.INK_2)
    ax.set_title(labels[attr], fontsize=11)
    ax.set_xlim(0, 70); ax.grid(axis="x"); ax.grid(axis="y", visible=False)
fig.suptitle("Churn rate by top drivers (dashed line = 26.5% average, red = above 40%)",
             x=0.01, ha="left", fontsize=13, fontweight="bold")
fig.tight_layout()
style.save(fig, FIG / "01_churn_drivers.png")

# %% [markdown]
# **Takeaway:** the strongest drivers are **contract type, tenure, internet service and payment method**.
# Gender has no effect, which is a useful negative result: the problem is commercial and operational, not demographic.
# * Month-to-month customers churn at **43%** vs **3%** on two-year contracts.
# * **Electronic check** payers churn at **45%**, nearly 3x customers paying by automatic card or bank transfer.
# * Customers **without online security or tech support** churn about twice as often.

# %% [markdown]
# ## 3. Customer lifecycle: when do customers leave?

# %%
heat = run_sql("02_churn_by_contract_tenure.sql").pivot(index="contract", columns="tenure_band", values="churn_rate_pct")
heat = heat[order["tenure_band"]]
surv = run_sql("07_cohort_survival.sql")

fig, axes = plt.subplots(1, 2, figsize=(13, 4), gridspec_kw={"width_ratios": [1.2, 1]})
ax = axes[0]
im = ax.imshow(heat.values, cmap=plt.matplotlib.colors.LinearSegmentedColormap.from_list(
    "seq", ["#cde2fb", "#6da7ec", "#256abf", "#0d366b"]), aspect="auto", vmin=0, vmax=60)
ax.set_xticks(range(heat.shape[1]), heat.columns); ax.set_yticks(range(heat.shape[0]), heat.index)
for i in range(heat.shape[0]):
    for j in range(heat.shape[1]):
        v = heat.values[i, j]
        ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=10, color="white" if v > 25 else style.INK)
ax.set_title("Churn rate: contract x tenure"); ax.grid(False)
for s_ in ax.spines.values(): s_.set_visible(False)
ax = axes[1]
ax.plot(surv.month, surv.month_to_month_pct, color=style.ORANGE, marker="o", ms=4, label="Month-to-month")
ax.plot(surv.month, surv.term_contract_pct, color=style.BLUE, marker="o", ms=4, label="1 or 2-year contract")
ax.set_title("Share of customers still active by tenure")
ax.set_xlabel("Months since joining"); ax.set_ylabel("% still active"); ax.set_ylim(50, 102)
ax.text(surv.month.iloc[-1], surv.month_to_month_pct.iloc[-1] - 3, f"{surv.month_to_month_pct.iloc[-1]:.0f}%",
        ha="right", color=style.INK_2); ax.legend(loc="lower left")
fig.tight_layout()
style.save(fig, FIG / "02_lifecycle.png")
heat

# %% [markdown]
# **Takeaway:** the **first 6 months on a month-to-month plan** is the danger zone, where **55%** of customers leave.
# Customers on term contracts almost never churn early. Onboarding and early contract conversion are the two biggest levers.

# %% [markdown]
# ## 4. Deep dive: why does the premium fibre product churn the most?
# Fibre is the most advanced and most expensive product, yet it has the **highest churn (42%)**. As an
# electronics & communications engineer, this is the result I would investigate first: customers pay
# more for a product that should be better. Is the fibre effect real, or is it explained by other factors?

# %%
fibre = run_sql("03_internet_service_quality.sql")
fibre["tech_support"] = fibre["tech_support"].map({"Yes": "With tech support", "No": "No tech support"})

# Same comparison within month-to-month customers only, to remove the contract effect
m2m = df[(df.contract == "Month-to-month") & (df.internet_service != "No")]
within = (m2m.groupby(["internet_service", "tenure_band"])["churned"].mean().mul(100)
             .unstack()[order["tenure_band"]].round(1))

fig, ax = plt.subplots(figsize=(8, 3.8))
x = np.arange(len(order["tenure_band"]))
for i, (svc, color) in enumerate([("DSL", style.BLUE), ("Fiber optic", style.ORANGE)]):
    ax.bar(x + (i - 0.5) * 0.36, within.loc[svc], width=0.34, color=color, label=svc)
ax.set_xticks(x, order["tenure_band"])
ax.set_title("Fibre churns more than DSL at every tenure (month-to-month only)")
ax.set_xlabel("Tenure"); ax.set_ylabel("Churn rate (%)"); ax.legend()
style.save(fig, FIG / "03_fibre_vs_dsl.png")
print("Churn by internet service and tech support:")
print(fibre.to_string(index=False), "\n")
within

# %% [markdown]
# **Takeaway:**
# * Fibre churns more than DSL **at every tenure, even among month-to-month customers**, so the effect is not
#   explained by contract or customer age.
# * Fibre customers **without tech support churn at 49%**, against 23% with support. Support roughly **halves** fibre churn.
# * Fibre costs about $88 to $101 a month, roughly $36 more than DSL for the same support level.
#
# **Hypothesis for the network team:** fibre customers have higher expectations and may experience
# installation or reliability issues (router configuration, outages, speed below advertised). This dataset has
# no network data, so the **next step** is to join churn with network KPIs such as outage minutes, latency,
# speed-test results and support tickets per customer. That is a concrete data request I would raise as an analyst.

# %%
bundle = run_sql("05_service_bundle_stickiness.sql")
pay = run_sql("04_payment_friction.sql")
pay

# %% [markdown]
# ## 5. Churn prediction model
# Two models with a stratified 80/20 train/test split:
# * **Logistic regression**: interpretable. Its coefficients become **odds ratios** the business can understand.
# * **Gradient boosting** (HistGradientBoosting): usually more accurate on tabular data.

# %%
num = ["tenure_months", "monthly_charges", "total_charges", "services_count"]
cat = [c for c in categorical if c != "tenure_band"]
X = df[num + cat]
X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)

prep = ColumnTransformer([("num", StandardScaler(), num),
                          ("cat", OneHotEncoder(drop="if_binary", handle_unknown="ignore"), cat)])
logit = make_pipeline(prep, LogisticRegression(C=1.0, max_iter=2000)).fit(X_tr, y_tr)

prep_gb = ColumnTransformer([("num", "passthrough", num),
                             ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat)])
gbm = make_pipeline(prep_gb, HistGradientBoostingClassifier(
    learning_rate=0.05, max_iter=300, max_leaf_nodes=15, l2_regularization=1.0, random_state=42)).fit(X_tr, y_tr)

scores = {"Logistic regression": logit.predict_proba(X_te)[:, 1], "Gradient boosting": gbm.predict_proba(X_te)[:, 1]}
perf = pd.DataFrame({name: {"ROC AUC": roc_auc_score(y_te, s), "PR AUC": average_precision_score(y_te, s),
                            "Top-decile churn rate": y_te.values[np.argsort(-s)][: len(s) // 10].mean(),
                            "Lift in top decile": y_te.values[np.argsort(-s)][: len(s) // 10].mean() / y_te.mean()}
                     for name, s in scores.items()}).T
perf.round(3)

# %% [markdown]
# Both models perform about the same (ROC AUC ≈ 0.84). When accuracy is equal, I choose the **logistic regression**
# because it is simpler to explain, audit and deploy. Its **top 10% riskiest customers churn at more than 2.5x the average rate**.
#
# ### What moves the odds of churn? (logistic regression odds ratios)

# %%
names = logit[0].get_feature_names_out()
coefs = pd.Series(logit[-1].coef_[0], index=names)
odds = np.exp(coefs).sort_values()
pretty = lambda n: n.replace("cat__", "").replace("num__", "").replace("_", " ")
show = pd.concat([odds.head(6), odds.tail(6)])

fig, ax = plt.subplots(figsize=(8, 5))
ax.barh([pretty(n) for n in show.index], show.values - 1, left=1,
        color=[style.BLUE if v < 1 else style.CRITICAL for v in show.values], height=0.6)
ax.axvline(1, color=style.INK_2, lw=0.8)
ax.set_xscale("log")
ax.set_xticks([0.3, 0.5, 0.7, 1, 1.5, 2, 2.5], ["0.3", "0.5", "0.7", "1", "1.5", "2", "2.5"])
ax.minorticks_off()
ax.set_title("Odds ratios: what raises (red) or lowers (blue) churn risk")
ax.set_xlabel("Odds ratio (log scale; numeric features per 1 standard deviation)")
ax.grid(axis="x"); ax.grid(axis="y", visible=False)
style.save(fig, FIG / "04_odds_ratios.png")
show.round(2).rename("odds_ratio").to_frame()

# %% [markdown]
# **Reading the odds ratios:** an odds ratio of 0.5 halves the odds of churning and 2.0 doubles them. Longer
# tenure and two-year contracts are the strongest protectors, while **fibre service (2.3x)** and month-to-month
# contracts raise risk.
# The model confirms the descriptive findings while controlling for all other factors.

# %% [markdown]
# ## 6. Retention targeting: who to contact, and is it profitable?
# For each customer in the test set:
#
# **Expected value of contacting = P(churn) × save rate × 12-month margin − offer cost**
#
# I compare four strategies on the same budget logic: contact nobody, contact everyone, contact a random 20%,
# or contact only customers whose expected value is positive.

# %%
test = X_te.copy()
test["churned"] = y_te.values
test["p_churn"] = scores["Logistic regression"]
test["value_12m"] = test["monthly_charges"] * VALUE_HORIZON_MONTHS * GROSS_MARGIN
test["expected_value"] = test["p_churn"] * SAVE_RATE * test["value_12m"] - OFFER_COST

def realised_profit(mask):
    """Profit using actual outcomes: only real churners can be saved."""
    t = test[mask]
    return (t["churned"] * SAVE_RATE * t["value_12m"]).sum() - OFFER_COST * len(t)

rng = np.random.default_rng(0)
strategies = {
    "Contact everyone": np.ones(len(test), bool),
    "Random 20%": rng.random(len(test)) < 0.20,
    "Top 20% by churn risk": test["p_churn"] >= test["p_churn"].quantile(0.80),
    "Positive expected value": test["expected_value"] > 0,
}
scale = len(df) / len(test)    # scale test-set results up to the full customer base
roi = pd.DataFrame({name: {"customers contacted": int(m.sum() * scale),
                           "churners reached": int(test.loc[m, "churned"].sum() * scale),
                           "profit": realised_profit(m) * scale} for name, m in strategies.items()}).T
roi["profit per contact"] = roi["profit"] / roi["customers contacted"]
roi_fmt = roi.copy()
roi_fmt["profit"] = roi_fmt["profit"].map("${:,.0f}".format)
roi_fmt["profit per contact"] = roi_fmt["profit per contact"].map("${:,.2f}".format)
roi.to_csv(ROOT / "reports/retention_strategy_roi.csv")
roi_fmt

# %%
fig, ax = plt.subplots(figsize=(8, 3.6))
colors = [style.CRITICAL if v < 0 else (style.AQUA if n == "Positive expected value" else style.BLUE)
          for n, v in roi["profit"].items()]
ax.barh(roi.index[::-1], roi["profit"][::-1] / 1000, color=colors[::-1], height=0.55)
ax.axvline(0, color=style.AXIS, lw=0.8)
for i, v in enumerate(roi["profit"][::-1] / 1000):
    ax.text(v + (2 if v >= 0 else -2), i, (f"${v:,.0f}k" if v >= 0 else f"-${-v:,.0f}k"), va="center", ha="left" if v >= 0 else "right",
            fontsize=9, color=style.INK_2)
ax.set_title("Retention campaign profit by targeting strategy (12-month margin)")
ax.set_xlabel("Profit ($ thousands, scaled to full customer base)")
ax.grid(axis="x"); ax.grid(axis="y", visible=False)
xmin, xmax = ax.get_xlim(); ax.set_xlim(xmin * 1.25 if xmin < 0 else xmin, xmax * 1.2)
style.save(fig, FIG / "05_targeting_roi.png")

# %% [markdown]
# **Takeaway:** contacting everyone wastes money on customers who were never going to leave. **Model-based
# targeting makes the campaign profitable**, and the expected-value rule maximises profit because it weighs
# both *risk* and *customer value*.

# %% [markdown]
# ### Customer segments for the retention team
# Combining churn risk with customer value gives four segments with a clear action for each.

# %%
all_scores = logit.predict_proba(X)[:, 1]
seg = df[["customer_id", "monthly_charges", "contract", "tenure_months", "churned"]].copy()
seg["p_churn"] = all_scores
high_risk = seg["p_churn"] >= 0.5
high_value = seg["monthly_charges"] >= seg["monthly_charges"].median()
seg["segment"] = np.select(
    [high_risk & high_value, high_risk & ~high_value, ~high_risk & high_value],
    ["1 Save now (high risk, high value)", "2 Low-cost nurture (high risk, low value)",
     "3 Protect & upsell (low risk, high value)"], "4 Maintain (low risk, low value)")
seg_summary = seg.groupby("segment").agg(customers=("customer_id", "count"),
                                         avg_monthly_charge=("monthly_charges", "mean"),
                                         actual_churn_rate=("churned", "mean"),
                                         mrr=("monthly_charges", "sum"))
seg_summary["share_of_mrr"] = seg_summary["mrr"] / seg_summary["mrr"].sum()
seg[seg.churned == 0].sort_values("p_churn", ascending=False).head(500).to_csv(
    ROOT / "reports/retention_target_list_top500.csv", index=False)
seg_summary.round(3)

# %% [markdown]
# ## 7. A/B test design: proving the offer works
# The save rate (30%) is an assumption. Before a full rollout, run a **randomised controlled test** on the
# "Save now" segment: half get the offer and half are a holdout. How many customers do we need?

# %%
def sample_size_two_proportions(p1, p2, alpha=0.05, power=0.80):
    z_a, z_b = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    p_bar = (p1 + p2) / 2
    n = ((z_a * np.sqrt(2 * p_bar * (1 - p_bar)) + z_b * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / (p1 - p2) ** 2
    return int(np.ceil(n))

baseline = seg_summary.loc["1 Save now (high risk, high value)", "actual_churn_rate"]
ab = pd.DataFrame([{"baseline churn": baseline, "target churn": baseline * (1 - r), "relative reduction": r,
                    "customers per group": sample_size_two_proportions(baseline, baseline * (1 - r))}
                   for r in [0.10, 0.15, 0.20, 0.30]])
ab.round(3)

# %% [markdown]
# **Test plan:** randomise the "Save now" segment 50/50 and run for 90 days. The **primary metric** is 90-day churn
# rate. **Guardrails** are revenue per customer (discount cost) and complaint rate. Detecting a 20% relative
# reduction needs about the number of customers shown per group, which fits within the segment size.

# %% [markdown]
# ## 8. Recommendations
#
# | # | Recommendation | Evidence | Owner |
# |---|---|---|---|
# | 1 | **Convert month-to-month customers to 1-year contracts** in months 1 to 6, with a loyalty discount | 55% churn in first 6 months on monthly plans vs about 10% on 1-year contracts | Commercial |
# | 2 | **Move electronic-check payers to automatic payment** (small credit for switching) | 45% churn vs 15-17% on automatic payment | Billing / CX |
# | 3 | **Bundle tech support and online security into fibre plans** | Fibre churn 49% without tech support vs 23% with | Product |
# | 4 | **Investigate fibre service quality.** Join churn with outage, latency and ticket data | Fibre churns more at every tenure, even after controlling for contract | Network engineering + Analytics |
# | 5 | **Run model-targeted retention** on the "Save now" segment, validated by an A/B test | Profitable vs loss-making "contact everyone" approach | Retention / CRM |
#
# **Limitations:** single snapshot, not a time series, so tenure is used as a lifecycle proxy. No network-quality or
# complaint data. Retention economics (offer cost, save rate, margin) are assumptions to be validated by the A/B test.
