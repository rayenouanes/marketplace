-- =====================================================================
-- test_idempotence_local.sql : test avec de FAUSSES données
-- Sert à vérifier ses tables et sa règle anti-doublons SANS attendre
-- le travail de Cris et Rayen. Ne pas lancer en production.
-- Résultat attendu : 2 lignes au 1er passage, 2 lignes au 2e passage.
-- =====================================================================

-- 1. Nettoyage des fausses données d'un test précédent
DELETE FROM dwh.fact_orders   WHERE order_id IN (1001, 1002);
DELETE FROM staging.orders    WHERE order_id IN (1001, 1002);
DELETE FROM dwh.dim_product   WHERE product_id = 455;
DELETE FROM dwh.dim_seller    WHERE seller_id = 12;

-- 2. Fausses données
INSERT INTO dwh.dim_seller  VALUES (12, 'Atelier Lune', 'France', '2025-01-01');
INSERT INTO dwh.dim_product VALUES (455, 'Bol en céramique', 'Cuisine', 12);
INSERT INTO staging.orders (order_id, dt, seller_id, product_id, quantity, unit_price)
VALUES (1001, '2026-04-07', 12, 455, 2, 15.00),
       (1002, '2026-04-07', 12, 455, 1, 15.00);

-- 3. Premier passage de la transformation
BEGIN;
DELETE FROM dwh.fact_orders WHERE dt = '2026-04-07';
INSERT INTO dwh.fact_orders (order_id, dt, seller_id, product_id, quantity, total, commission)
SELECT order_id, dt, seller_id, product_id, quantity,
       quantity * unit_price, ROUND(quantity * unit_price * 0.12, 2)
FROM staging.orders WHERE dt = '2026-04-07';
COMMIT;

SELECT 'Passage 1' AS test, COUNT(*) AS nb_lignes FROM dwh.fact_orders WHERE dt = '2026-04-07';

-- 4. Deuxième passage (identique) : le nombre de lignes ne doit PAS doubler
BEGIN;
DELETE FROM dwh.fact_orders WHERE dt = '2026-04-07';
INSERT INTO dwh.fact_orders (order_id, dt, seller_id, product_id, quantity, total, commission)
SELECT order_id, dt, seller_id, product_id, quantity,
       quantity * unit_price, ROUND(quantity * unit_price * 0.12, 2)
FROM staging.orders WHERE dt = '2026-04-07';
COMMIT;

SELECT 'Passage 2' AS test, COUNT(*) AS nb_lignes FROM dwh.fact_orders WHERE dt = '2026-04-07';