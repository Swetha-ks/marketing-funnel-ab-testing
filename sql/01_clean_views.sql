-- 01_clean_views.sql
-- Data cleaning layer. Raw tables are never modified; analysis reads the clean_* views.
-- Issues found during profiling (see src/analysis.py -> data_quality_report):
--   users  : duplicate user_id rows, NULL device, 'unknown' city_tier
--   orders : duplicate order_id rows, negative order values, extreme outliers (> 20,000 INR)

DROP VIEW IF EXISTS clean_users;
CREATE VIEW clean_users AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY first_visit_date) AS rn
    FROM users
)
SELECT user_id,
       campaign_id,
       DATE(first_visit_date)                              AS first_visit_date,
       COALESCE(device, 'Unknown')                         AS device,
       CASE WHEN city_tier = 'unknown' THEN 'Unknown' ELSE city_tier END AS city_tier,
       ab_variant
FROM ranked
WHERE rn = 1;

DROP VIEW IF EXISTS clean_orders;
CREATE VIEW clean_orders AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_date) AS rn
    FROM orders
)
SELECT order_id, user_id, DATE(order_date) AS order_date, order_value_inr
FROM ranked
WHERE rn = 1
  AND order_value_inr > 0
  AND order_value_inr <= 20000;

-- Funnel flags: one row per user, 1 if the user reached that stage.
DROP VIEW IF EXISTS user_funnel;
CREATE VIEW user_funnel AS
SELECT u.user_id,
       u.campaign_id,
       u.first_visit_date,
       u.device,
       u.city_tier,
       u.ab_variant,
       MAX(CASE WHEN e.stage = 'visit'        THEN 1 ELSE 0 END) AS visited,
       MAX(CASE WHEN e.stage = 'product_view' THEN 1 ELSE 0 END) AS viewed,
       MAX(CASE WHEN e.stage = 'add_to_cart'  THEN 1 ELSE 0 END) AS carted,
       MAX(CASE WHEN e.stage = 'checkout'     THEN 1 ELSE 0 END) AS checked_out,
       MAX(CASE WHEN e.stage = 'purchase'     THEN 1 ELSE 0 END) AS purchased
FROM clean_users u
LEFT JOIN funnel_events e ON e.user_id = u.user_id
GROUP BY u.user_id;
