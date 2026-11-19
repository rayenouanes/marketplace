-- =====================================================================
-- transform_fact_orders.sql : staging.orders -> dwh.fact_orders
-- Responsable : Lydia
-- Règle d'idempotence : on efface le jour, puis on le remet.
-- {{ ds }} est remplacé automatiquement par Airflow (ex : 2026-04-07).
-- =====================================================================

BEGIN;

DELETE FROM dwh.fact_orders
WHERE dt = '{{ ds }}';

INSERT INTO dwh.fact_orders (order_id, dt, seller_id, product_id, quantity, total, commission)
SELECT order_id,
       dt,
       seller_id,
       product_id,
       quantity,
       quantity * unit_price,
       ROUND(quantity * unit_price * 0.12, 2)
FROM staging.orders
WHERE dt = '{{ ds }}';

COMMIT;