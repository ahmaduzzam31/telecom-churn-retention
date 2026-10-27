-- Payment method and billing type: manual payment methods churn more than automatic ones.
SELECT
    b.payment_method,
    CASE WHEN b.payment_method LIKE '%automatic%' THEN 'Automatic' ELSE 'Manual' END AS payment_type,
    COUNT(*)                                AS customers,
    ROUND(100.0 * AVG(ch.churned), 1)       AS churn_rate_pct,
    ROUND(100.0 * AVG(ch.churned) - 100.0 * (SELECT AVG(churned) FROM churn), 1) AS vs_avg_pp
FROM billing b
JOIN churn ch USING (customer_id)
GROUP BY b.payment_method
ORDER BY churn_rate_pct DESC;
