-- =====================================================================
-- schema.sql : création des schémas et des tables du Data Warehouse
-- Responsable : Lydia (personne 3, PostgreSQL & Data Warehouse)
-- Les noms de colonnes de staging.orders sont à confirmer avec Cris.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 1. Les 3 schémas (les "dossiers")
-- ---------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS staging;    -- zone d'arrivée (données brutes typées)
CREATE SCHEMA IF NOT EXISTS dwh;        -- modèle en étoile (données rangées)
CREATE SCHEMA IF NOT EXISTS analytics;  -- résumés pour Metabase


-- ---------------------------------------------------------------------
-- 2. Zone d'arrivée : staging.orders (remplie par Cris)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS staging.orders (
    order_id    INTEGER,
    dt          DATE,
    seller_id   INTEGER,
    product_id  INTEGER,
    quantity    INTEGER,
    unit_price  NUMERIC(10,2),
    loaded_at   TIMESTAMP DEFAULT NOW()
);


-- ---------------------------------------------------------------------
-- 3. Dimensions (les tableaux qui décrivent)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.dim_seller (
    seller_id    INTEGER PRIMARY KEY,
    name         TEXT,
    country      TEXT,
    joined_date  DATE
);

CREATE TABLE IF NOT EXISTS dwh.dim_product (
    product_id  INTEGER PRIMARY KEY,
    name        TEXT,
    category    TEXT,
    seller_id   INTEGER REFERENCES dwh.dim_seller(seller_id)
);

CREATE TABLE IF NOT EXISTS dwh.dim_date (
    dt           DATE PRIMARY KEY,
    year         INTEGER,
    month        INTEGER,
    day          INTEGER,
    day_of_week  INTEGER       -- 1 = lundi ... 7 = dimanche
);


-- ---------------------------------------------------------------------
-- 4. Table de faits : une ligne = un produit vendu dans une commande
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dwh.fact_orders (
    order_id    INTEGER,
    dt          DATE    REFERENCES dwh.dim_date(dt),
    seller_id   INTEGER REFERENCES dwh.dim_seller(seller_id),
    product_id  INTEGER REFERENCES dwh.dim_product(product_id),
    quantity    INTEGER,
    total       NUMERIC(12,2),   -- quantity * unit_price
    commission  NUMERIC(12,2),   -- 12 % du total
    PRIMARY KEY (order_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_orders_dt ON dwh.fact_orders (dt);


-- ---------------------------------------------------------------------
-- 5. Table de résumé pour Metabase (une ligne par jour)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analytics.daily_summary (
    dt                DATE PRIMARY KEY,
    total_orders      INTEGER,
    total_revenue     NUMERIC(14,2),
    total_commission  NUMERIC(14,2),
    avg_basket        NUMERIC(10,2)
);


-- ---------------------------------------------------------------------
-- 6. Remplissage du calendrier (toute l'année 2026)
-- ---------------------------------------------------------------------
INSERT INTO dwh.dim_date (dt, year, month, day, day_of_week)
SELECT d::date,
       EXTRACT(YEAR   FROM d),
       EXTRACT(MONTH  FROM d),
       EXTRACT(DAY    FROM d),
       EXTRACT(ISODOW FROM d)
FROM generate_series('2026-01-01'::date, '2026-12-31'::date, '1 day') AS d
ON CONFLICT (dt) DO NOTHING;