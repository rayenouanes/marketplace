-- =====================================================================
-- DONNÉES DE DÉMO — usage LOCAL uniquement
-- But : construire les dashboards Metabase avant que le pipeline tourne.
--
-- Adapté au schéma de Lydia (init-db/schema.sql) : identifiants INTEGER.
-- PRÉREQUIS : avoir exécuté init-db/schema.sql AVANT ce script.
--
-- Les données de démo utilisent des identifiants ≥ 900000 pour ne jamais
-- se mélanger avec les vraies données de l'API :
--   vendeurs 900001-900040 · produits 900001-900200 · commandes ≥ 90000000
-- 40 vendeurs, 200 produits, 30 jours de ventes (09/03 → 07/04/2026).
-- Rejouable : relancer le script donne exactement le même résultat.
--
-- Lancement (PowerShell, depuis le dossier marketplace) :
--   Get-Content metabase\dev\seed_demo_data.sql | docker compose exec -T postgres-dwh psql -U marketplace -d marketplace
-- =====================================================================

BEGIN;

-- 1. Nettoyage d'une éventuelle démo précédente (ordre imposé par les FK)
DELETE FROM dwh.fact_orders WHERE order_id   >= 90000000;
DELETE FROM dwh.dim_product WHERE product_id >= 900000;
DELETE FROM dwh.dim_seller  WHERE seller_id  >= 900000;

SELECT setseed(0.42);

-- 2. 40 vendeurs (les 4 derniers cessent de vendre → "vendeurs inactifs")
INSERT INTO dwh.dim_seller (seller_id, name, country, joined_date)
SELECT
    900000 + i,
    (ARRAY['Atelier','Maison','Studio','Comptoir','Boutique'])[1 + (i % 5)]
        || ' ' ||
    (ARRAY['Lumière','Céleste','du Lin','Bohème','Terra','Azur','Sauvage','Nomade'])[1 + (i % 8)]
        || ' ' || i,
    (ARRAY['France','France','France','Belgique','Suisse','Espagne'])[1 + (i % 6)],
    DATE '2023-01-01' + (i * 17)
FROM generate_series(1, 40) AS i;

-- 3. 200 produits répartis dans 6 catégories
INSERT INTO dwh.dim_product (product_id, name, category, seller_id)
SELECT
    900000 + i,
    (ARRAY['Bougie','Tote bag','Bol','Carnet','Savon','Collier','Plaid','Affiche'])[1 + (i % 8)] || ' n°' || i,
    (ARRAY['Maison','Mode','Beauté','Papeterie','Bijoux','Déco'])[1 + (i % 6)],
    900000 + 1 + (i % 40)
FROM generate_series(1, 200) AS i;

-- 4. ~300 commandes/jour, plus le week-end, et une chute volontaire le
--    2026-04-01 (utile pour tester la détection d'anomalie en bonus)
--    dim_date est déjà rempli pour 2026 par le schema.sql de Lydia.
WITH jours AS (
    SELECT d::date AS dt,
           CASE WHEN d::date = DATE '2026-04-01' THEN 120
                WHEN EXTRACT(ISODOW FROM d) IN (6, 7) THEN 380
                ELSE 300 END AS nb
    FROM generate_series(DATE '2026-03-09', DATE '2026-04-07', INTERVAL '1 day') AS d
),
lignes AS (
    SELECT j.dt, n,
           1 + floor(power(random(), 2) * 200)::int AS p_idx,   -- quelques best-sellers
           1 + floor(random() * 3)::int             AS qty,
           round((5 + random() * 75)::numeric, 2)   AS unit_price
    FROM jours j, generate_series(1, j.nb) AS n
)
INSERT INTO dwh.fact_orders (order_id, dt, seller_id, product_id, quantity, total, commission)
SELECT
    90000000 + (l.dt - DATE '2026-03-09') * 1000 + l.n,
    l.dt,
    p.seller_id,
    p.product_id,
    l.qty,
    l.qty * l.unit_price,
    round(l.qty * l.unit_price * 0.12, 2)
FROM lignes l
JOIN dwh.dim_product p ON p.product_id = 900000 + l.p_idx
WHERE NOT (p.seller_id >= 900037 AND l.dt > DATE '2026-03-28');

-- 5. Résumé quotidien (uniquement pour les jours de démo, sans écraser de vraies données)
INSERT INTO analytics.daily_summary (dt, total_orders, total_revenue, total_commission, avg_basket)
SELECT dt,
       COUNT(DISTINCT order_id),
       SUM(total),
       SUM(commission),
       ROUND(SUM(total) / NULLIF(COUNT(DISTINCT order_id), 0), 2)
FROM dwh.fact_orders
WHERE order_id >= 90000000
GROUP BY dt
ON CONFLICT (dt) DO NOTHING;

COMMIT;

-- Contrôle
SELECT 'vendeurs' AS table_, COUNT(*) FROM dwh.dim_seller  WHERE seller_id  >= 900000
UNION ALL SELECT 'produits',  COUNT(*) FROM dwh.dim_product WHERE product_id >= 900000
UNION ALL SELECT 'commandes', COUNT(*) FROM dwh.fact_orders WHERE order_id   >= 90000000
UNION ALL SELECT 'jours',     COUNT(DISTINCT dt) FROM dwh.fact_orders WHERE order_id >= 90000000;

-- =====================================================================
-- POUR EFFACER LA DÉMO (avant de charger les vraies données) :
--   DELETE FROM analytics.daily_summary WHERE dt BETWEEN '2026-03-09' AND '2026-04-07';
--   DELETE FROM dwh.fact_orders WHERE order_id   >= 90000000;
--   DELETE FROM dwh.dim_product WHERE product_id >= 900000;
--   DELETE FROM dwh.dim_seller  WHERE seller_id  >= 900000;
-- =====================================================================
