-- =====================================================================
-- Dashboard 2 — Top Sellers
-- Même hypothèse de schéma que dashboard1 ; référence temporelle = MAX(dt).
-- =====================================================================

-- Q2.1 — Top 10 vendeurs du mois (visualisation : Bar chart)
SELECT
    s.name                      AS vendeur,
    SUM(f.total)                AS ca,
    SUM(f.commission)           AS commission_maelys,
    COUNT(DISTINCT f.order_id)  AS nb_commandes
FROM dwh.fact_orders f
JOIN dwh.dim_seller s ON s.seller_id = f.seller_id
WHERE date_trunc('month', f.dt) = date_trunc('month', (SELECT MAX(dt) FROM dwh.fact_orders))
GROUP BY s.name
ORDER BY ca DESC
LIMIT 10;


-- Q2.2 — Évolution du CA des top 3 vendeurs sur 30 jours
-- (visualisation : Line chart, X = dt, Y = ca, série = vendeur)
WITH ref AS (
    SELECT MAX(dt) AS max_dt FROM dwh.fact_orders
),
periode AS (
    SELECT f.*
    FROM dwh.fact_orders f, ref
    WHERE f.dt > ref.max_dt - INTERVAL '30 days'
),
top3 AS (
    SELECT seller_id
    FROM periode
    GROUP BY seller_id
    ORDER BY SUM(total) DESC
    LIMIT 3
)
SELECT
    p.dt,
    s.name       AS vendeur,
    SUM(p.total) AS ca
FROM periode p
JOIN top3 t        ON t.seller_id = p.seller_id
JOIN dwh.dim_seller s ON s.seller_id = p.seller_id
GROUP BY p.dt, s.name
ORDER BY p.dt, s.name;


-- Q2.3 — Vendeurs inactifs (> 7 jours sans vente) (visualisation : Table)
-- Inclut les vendeurs qui n'ont JAMAIS vendu (LEFT JOIN).
WITH ref AS (
    SELECT MAX(dt) AS max_dt FROM dwh.fact_orders
),
derniere_vente AS (
    SELECT seller_id, MAX(dt) AS last_sale_dt
    FROM dwh.fact_orders
    GROUP BY seller_id
)
SELECT
    s.seller_id,
    s.name          AS vendeur,
    s.country       AS pays,
    d.last_sale_dt  AS derniere_vente,
    (ref.max_dt - d.last_sale_dt) AS jours_sans_vente
FROM dwh.dim_seller s
CROSS JOIN ref
LEFT JOIN derniere_vente d ON d.seller_id = s.seller_id
WHERE d.last_sale_dt IS NULL
   OR d.last_sale_dt < ref.max_dt - 7
ORDER BY d.last_sale_dt NULLS FIRST;
