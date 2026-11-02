-- 05_weekly_trend.sql
-- Q4. Weekly traffic, orders and revenue, with 4-week rolling average of conversion.
WITH weekly AS (
    SELECT STRFTIME('%Y-%W', first_visit_date)  AS year_week,
           MIN(first_visit_date)                AS week_start,
           COUNT(*)                             AS visitors,
           SUM(purchased)                       AS buyers
    FROM user_funnel
    GROUP BY year_week
)
SELECT year_week,
       week_start,
       visitors,
       buyers,
       ROUND(100.0 * buyers / visitors, 2) AS conv_pct,
       ROUND(AVG(100.0 * buyers / visitors) OVER (
             ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW), 2) AS conv_4wk_avg_pct
FROM weekly
ORDER BY week_start;
