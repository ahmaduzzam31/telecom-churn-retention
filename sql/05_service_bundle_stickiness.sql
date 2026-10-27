-- More services = stickier customers? Churn rate and revenue by number of services held.
SELECT
    s.services_count,
    COUNT(*)                                AS customers,
    ROUND(100.0 * AVG(ch.churned), 1)       AS churn_rate_pct,
    ROUND(AVG(b.monthly_charges), 2)        AS avg_monthly_charge
FROM subscriptions s
JOIN billing b  USING (customer_id)
JOIN churn  ch USING (customer_id)
GROUP BY s.services_count
ORDER BY s.services_count;
