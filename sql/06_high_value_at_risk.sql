-- Retention target list: active customers in the top revenue quartile who match the
-- highest-risk profile (month-to-month, under 12 months tenure, no tech support).
WITH active AS (
    SELECT c.customer_id, c.tenure_months, b.contract, b.payment_method,
           b.monthly_charges, s.internet_service, s.tech_support,
           NTILE(4) OVER (ORDER BY b.monthly_charges DESC) AS revenue_quartile
    FROM customers c
    JOIN billing b       USING (customer_id)
    JOIN subscriptions s USING (customer_id)
    JOIN churn ch        USING (customer_id)
    WHERE ch.churned = 0
)
SELECT customer_id, tenure_months, contract, internet_service, payment_method, monthly_charges
FROM active
WHERE revenue_quartile = 1
  AND contract = 'Month-to-month'
  AND tenure_months < 12
  AND tech_support = 'No'
ORDER BY monthly_charges DESC;
