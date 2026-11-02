-- 02_funnel_analysis.sql
-- Q1. Overall funnel with step-to-step and cumulative conversion.
WITH totals AS (
    SELECT SUM(visited) AS visit, SUM(viewed) AS view, SUM(carted) AS cart,
           SUM(checked_out) AS checkout, SUM(purchased) AS purchase
    FROM user_funnel
),
stages AS (
    SELECT 1 AS step, 'Visit'        AS stage, visit    AS users FROM totals UNION ALL
    SELECT 2, 'Product view',  view     FROM totals UNION ALL
    SELECT 3, 'Add to cart',   cart     FROM totals UNION ALL
    SELECT 4, 'Checkout',      checkout FROM totals UNION ALL
    SELECT 5, 'Purchase',      purchase FROM totals
)
SELECT step,
       stage,
       users,
       ROUND(100.0 * users / LAG(users) OVER (ORDER BY step), 2)       AS step_conv_pct,
       ROUND(100.0 * users / FIRST_VALUE(users) OVER (ORDER BY step), 2) AS cumulative_conv_pct
FROM stages
ORDER BY step;
