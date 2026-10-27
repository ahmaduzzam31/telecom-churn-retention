-- Headline KPIs: customers, churn rate, monthly recurring revenue (MRR) and MRR lost to churn.
SELECT
    COUNT(*)                                                   AS customers,
    SUM(ch.churned)                                            AS churned_customers,
    ROUND(100.0 * AVG(ch.churned), 1)                          AS churn_rate_pct,
    ROUND(SUM(b.monthly_charges), 0)                           AS total_mrr,
    ROUND(SUM(b.monthly_charges * ch.churned), 0)              AS mrr_lost,
    ROUND(100.0 * SUM(b.monthly_charges * ch.churned) / SUM(b.monthly_charges), 1) AS mrr_lost_pct,
    ROUND(AVG(b.monthly_charges), 2)                           AS arpu
FROM customers c
JOIN billing b  USING (customer_id)
JOIN churn  ch USING (customer_id);
