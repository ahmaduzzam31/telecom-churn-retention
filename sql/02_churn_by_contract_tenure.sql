-- Churn heatmap: contract type x tenure band. Shows where in the lifecycle customers leave.
SELECT
    b.contract,
    c.tenure_band,
    COUNT(*)                           AS customers,
    ROUND(100.0 * AVG(ch.churned), 1)  AS churn_rate_pct
FROM customers c
JOIN billing b  USING (customer_id)
JOIN churn  ch USING (customer_id)
GROUP BY b.contract, c.tenure_band
ORDER BY b.contract,
         CASE c.tenure_band WHEN '0-6 m' THEN 1 WHEN '7-12 m' THEN 2 WHEN '13-24 m' THEN 3
                            WHEN '25-48 m' THEN 4 ELSE 5 END;
