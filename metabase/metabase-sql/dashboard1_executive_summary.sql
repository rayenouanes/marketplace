-- =====================================================================
-- Dashboard 1 — Executive Summary
-- Hypothèse de schéma (à aligner avec Lydia, feature/data-warehouse) :
--   dwh.fact_orders (order_id, dt, seller_id, product_id, quantity, total, commission)
--   dwh.dim_seller  (seller_id, name, country, joined_date)
-- ⚠️ "Aujourd'hui" = dernière date chargée (MAX(dt)), pas CURRENT_DATE :
--    les données sont rejouées sur des dates passées (ex. 2026-04-07),
--    CURRENT_DATE donnerait un dashboard vide.
-- =====================================================================

-- Q1.1 — KPI "CA total du jour" (visualisation : Big Number / Nombre)
SELECT
    SUM(f.total)                AS ca_du_jour,
    COUNT(DISTINCT f.order_id)  AS nb_commandes,
    ROUND(SUM(f.total) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS panier_moyen
FROM dwh.fact_orders f
WHERE f.dt = (SELECT MAX(dt) FROM dwh.fact_orders);


-- Q1.2 — CA des 30 derniers jours (visualisation : Line chart, X = dt, Y = ca)
SELECT
    f.dt,
    SUM(f.total) AS ca
FROM dwh.fact_orders f
WHERE f.dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
GROUP BY f.dt
ORDER BY f.dt;

-- Variante si analytics.daily_summary existe (plus rapide, recommandé) :
-- SELECT dt, total_revenue AS ca
-- FROM analytics.daily_summary
-- WHERE dt > (SELECT MAX(dt) FROM analytics.daily_summary) - INTERVAL '30 days'
-- ORDER BY dt;


-- Q1.3 — Top 10 vendeurs du jour (visualisation : Bar chart / Row chart)
SELECT
    s.name       AS vendeur,
    SUM(f.total) AS ca
FROM dwh.fact_orders f
JOIN dwh.dim_seller s ON s.seller_id = f.seller_id
WHERE f.dt = (SELECT MAX(dt) FROM dwh.fact_orders)
GROUP BY s.name
ORDER BY ca DESC
LIMIT 10;
