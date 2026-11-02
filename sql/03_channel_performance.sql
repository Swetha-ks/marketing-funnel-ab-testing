-- 03_channel_performance.sql
-- Q2. Which channels actually pay back? Conversion, revenue, CAC, ROAS, profit proxy.
WITH spend AS (
    SELECT channel, SUM(spend_inr) AS spend
    FROM campaigns
    GROUP BY channel
),
perf AS (
    SELECT c.channel,
           COUNT(DISTINCT f.user_id)                      AS visitors,
           SUM(f.purchased)                               AS buyers,
           COUNT(o.order_id)                              AS orders,
           ROUND(SUM(COALESCE(o.order_value_inr, 0)), 0)  AS revenue
    FROM user_funnel f
    JOIN campaigns c        ON c.campaign_id = f.campaign_id
    LEFT JOIN clean_orders o ON o.user_id = f.user_id
    GROUP BY c.channel
)
SELECT p.channel,
       p.visitors,
       p.buyers,
       ROUND(100.0 * p.buyers / p.visitors, 2)                          AS conv_rate_pct,
       p.revenue,
       ROUND(p.revenue / NULLIF(p.orders, 0), 0)                        AS aov,
       s.spend,
       ROUND(s.spend / NULLIF(p.buyers, 0), 0)                          AS cac,
       ROUND(p.revenue / NULLIF(s.spend, 0), 2)                         AS roas,
       ROUND(p.revenue - s.spend, 0)                                    AS revenue_minus_spend,
       RANK() OVER (ORDER BY p.revenue / NULLIF(s.spend, 0) DESC)       AS roas_rank
FROM perf p
JOIN spend s ON s.channel = p.channel
ORDER BY p.revenue DESC;
