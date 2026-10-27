# Executive Summary: Customer Churn & Retention

**To:** Chief Commercial Officer, Head of Customer Experience
**Re:** Why customers leave and a profitable plan to keep them
**Data:** 7,043 customers: services, contracts, billing and churn status (IBM Telco dataset)

## Situation
**26.5%** of customers churned, taking **$139k of monthly recurring revenue (30.5% of MRR)**. Churners pay more
than average, so every point of churn costs disproportionate revenue.

## Key findings
1. **The first six months decide everything.** Month-to-month customers churn at **55%** in months 0 to 6. On a
   1-year contract the rate is about **10%**, and on a 2-year contract it is close to **0%**.
2. **The premium fibre product has a retention problem.** Fibre churns at **42%**, against 19% for DSL, and it
   churns more **at every tenure** even among month-to-month customers. Fibre customers **without tech support churn at 49%**
   and those with it at 23%.
3. **Payment friction drives exits.** Electronic-check payers churn at **45%**, against **15 to 17%** on automatic payment.
4. **Demographics are not the issue.** Gender has no effect, so the drivers are commercial and operational and can be fixed.
5. **Churn is predictable.** A logistic regression scores **ROC AUC 0.84**. Its top 10% riskiest customers churn
   at **2.9x** the average rate.

## Retention economics (assumed $60 offer cost, 30% save rate, 12-month margin)
| Strategy | Customers contacted | Campaign profit |
|---|---|---|
| Contact everyone | 7,043 | **−$129k** |
| Random 20% | 1,419 | −$21k |
| Top 20% by churn risk | 1,409 | +$76k |
| **Positive expected value (risk × value)** | **2,109** | **+$85k** |

## Recommendations
| # | Action | Owner |
|---|---|---|
| 1 | Offer month-to-month customers a 1-year contract with a loyalty discount in months 1 to 6 | Commercial |
| 2 | Give a one-off credit for switching from electronic check to automatic payment | Billing / CX |
| 3 | Bundle tech support and online security into fibre plans | Product |
| 4 | Join churn data with network KPIs (outages, latency, tickets) to find the fibre root cause | Network Eng. + Analytics |
| 5 | Run model-targeted retention on the 1,263-customer "Save now" segment, as a 50/50 A/B test (≈214 per arm detects a 20% reduction) | CRM / Analytics |
