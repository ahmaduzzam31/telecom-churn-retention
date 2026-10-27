-- Retention curve: of customers who reached each tenure milestone, what share is still active?
-- (Cross-sectional snapshot: churned customers' tenure = months until they left.)
WITH milestones AS (SELECT UNNEST([1, 3, 6, 12, 24, 36, 48, 60, 72]) AS month),
base AS (
    SELECT b.contract, c.tenure_months, ch.churned
    FROM customers c JOIN billing b USING (customer_id) JOIN churn ch USING (customer_id)
)
SELECT
    m.month,
    ROUND(100.0 * SUM(CASE WHEN b.contract = 'Month-to-month' AND (b.tenure_months >= m.month OR b.churned = 0) THEN 1 END)
          / SUM(CASE WHEN b.contract = 'Month-to-month' THEN 1 END), 1) AS month_to_month_pct,
    ROUND(100.0 * SUM(CASE WHEN b.contract <> 'Month-to-month' AND (b.tenure_months >= m.month OR b.churned = 0) THEN 1 END)
          / SUM(CASE WHEN b.contract <> 'Month-to-month' THEN 1 END), 1) AS term_contract_pct
FROM milestones m CROSS JOIN base b
GROUP BY m.month
ORDER BY m.month;
