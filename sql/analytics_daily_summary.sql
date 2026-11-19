-- =====================================================================
-- analytics_daily_summary.sql : dwh.fact_orders -> analytics.daily_summary
-- Responsable : Lydia
-- Même règle : on efface le jour, puis on le recalcule.
-- =====================================================================

BEGIN;

DELETE FROM analytics.daily_summary
WHERE dt = '{{ ds }}';

INSERT INTO analytics.daily_summary (dt, total_orders, total_revenue, total_commission, avg_basket)
SELECT dt,
       COUNT(DISTINCT order_id),
       SUM(total),
       SUM(commission),
       ROUND(SUM(total) / NULLIF(COUNT(DISTINCT order_id), 0), 2)
FROM dwh.fact_orders
WHERE dt = '{{ ds }}'
GROUP BY dt;

COMMIT;