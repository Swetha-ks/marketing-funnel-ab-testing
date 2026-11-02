-- 04_segment_analysis.sql
-- Q3. Where does the funnel leak? Conversion by device and city tier.
SELECT device,
       COUNT(*)                                                           AS visitors,
       ROUND(100.0 * SUM(viewed)      / COUNT(*), 2)                      AS view_rate_pct,
       ROUND(100.0 * SUM(carted)      / NULLIF(SUM(viewed), 0), 2)        AS view_to_cart_pct,
       ROUND(100.0 * SUM(checked_out) / NULLIF(SUM(carted), 0), 2)        AS cart_to_checkout_pct,
       ROUND(100.0 * SUM(purchased)   / NULLIF(SUM(checked_out), 0), 2)   AS checkout_to_buy_pct,
       ROUND(100.0 * SUM(purchased)   / COUNT(*), 2)                      AS overall_conv_pct
FROM user_funnel
GROUP BY device
ORDER BY visitors DESC;
