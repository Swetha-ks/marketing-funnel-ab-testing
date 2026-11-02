-- 06_ab_test_summary.sql
-- Q5. Raw A/B test counts. Statistical testing is done in src/analysis.py.
-- Primary metric : purchase conversion per visitor
-- Guardrail      : revenue per visitor
SELECT f.ab_variant,
       COUNT(*)                                        AS visitors,
       SUM(f.purchased)                                AS buyers,
       ROUND(100.0 * SUM(f.purchased) / COUNT(*), 3)   AS conv_pct,
       ROUND(SUM(COALESCE(o.order_value_inr, 0)) / COUNT(*), 2) AS revenue_per_visitor
FROM user_funnel f
LEFT JOIN clean_orders o ON o.user_id = f.user_id
GROUP BY f.ab_variant;
