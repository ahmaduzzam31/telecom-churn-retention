-- Fibre vs DSL: does the premium (fibre) product churn more, and do support add-ons help?
SELECT
    s.internet_service,
    s.tech_support,
    COUNT(*)                                AS customers,
    ROUND(AVG(b.monthly_charges), 2)        AS avg_monthly_charge,
    ROUND(100.0 * AVG(ch.churned), 1)       AS churn_rate_pct
FROM subscriptions s
JOIN billing b  USING (customer_id)
JOIN churn  ch USING (customer_id)
WHERE s.internet_service <> 'No'
GROUP BY s.internet_service, s.tech_support
ORDER BY s.internet_service, s.tech_support;
