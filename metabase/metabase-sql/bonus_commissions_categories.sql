-- =====================================================================
-- BONUS (Should, +5 pts) — à ne faire QU'APRÈS le MVP validé
-- Dashboard 3 — Commissions (US-03) / Dashboard 4 — Catégories (US-04)
-- =====================================================================

-- Q3.1 — Commissions par jour, 30 derniers jours (Line ou Bar chart)
SELECT
    f.dt,
    SUM(f.total)      AS ca,
    SUM(f.commission) AS commission,
    ROUND(100.0 * SUM(f.commission) / NULLIF(SUM(f.total), 0), 2) AS taux_pct  -- doit ≈ 12 %
FROM dwh.fact_orders f
WHERE f.dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
GROUP BY f.dt
ORDER BY f.dt;

-- Q3.2 — Commissions du mois par vendeur (Table, pour la facturation)
SELECT
    s.name            AS vendeur,
    SUM(f.total)      AS ca,
    SUM(f.commission) AS commission_a_facturer
FROM dwh.fact_orders f
JOIN dwh.dim_seller s ON s.seller_id = f.seller_id
WHERE date_trunc('month', f.dt) = date_trunc('month', (SELECT MAX(dt) FROM dwh.fact_orders))
GROUP BY s.name
ORDER BY commission_a_facturer DESC;

-- Q4.1 — Répartition du CA par catégorie sur 30 jours (Pie / Bar chart)
SELECT
    p.category        AS categorie,
    SUM(f.total)      AS ca
FROM dwh.fact_orders f
JOIN dwh.dim_product p ON p.product_id = f.product_id
WHERE f.dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
GROUP BY p.category
ORDER BY ca DESC;
