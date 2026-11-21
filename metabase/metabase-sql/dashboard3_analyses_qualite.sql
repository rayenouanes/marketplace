-- =====================================================================
-- Dashboard 3 — Analyses avancées & qualité des données
-- Schéma : init-db/schema.sql (Lydia). Date de référence = MAX(dt).
-- Chaque requête indique : la visualisation Metabase, ce qu'elle montre,
-- le problème qu'elle révèle et la solution proposée.
-- =====================================================================


-- =====================================================================
-- PARTIE A — ANALYSES MÉTIER
-- =====================================================================

-- A1 — Alerte anomalie : CA du jour vs moyenne des 7 jours précédents (US-05)
-- Visualisation : Tableau (mise en forme conditionnelle : "Statut" = ALERTE en rouge)
-- Montre       : chaque jour, l'écart du CA à sa moyenne glissante 7 jours.
-- Problème     : une chute brutale (ex. 1er avril, ~ -60 %) passe inaperçue
--                dans un reporting Excel hebdomadaire.
-- Solution     : alerte automatique quand CA < 70 % de la moyenne 7 j
--                (DAG anomaly detection + notification Slack/email).
WITH jour AS (
    SELECT dt, SUM(total) AS ca
    FROM dwh.fact_orders
    GROUP BY dt
),
calc AS (
    SELECT dt,
           ca,
           AVG(ca) OVER (ORDER BY dt ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS moy_7j
    FROM jour
)
SELECT dt                                          AS "Date",
       ROUND(ca, 0)                                AS "CA du jour (€)",
       ROUND(moy_7j, 0)                            AS "Moyenne 7 j précédents (€)",
       ROUND(100.0 * ca / NULLIF(moy_7j, 0), 1)    AS "% de la moyenne",
       CASE WHEN ca < 0.7 * moy_7j THEN 'ALERTE'
            WHEN ca < 0.9 * moy_7j THEN 'À surveiller'
            ELSE 'Normal' END                      AS "Statut"
FROM calc
WHERE moy_7j IS NOT NULL
ORDER BY dt DESC;


-- A2 — Concentration du CA : courbe de Pareto des vendeurs
-- Visualisation : Ligne (X = "Rang vendeur", Y = "% CA cumulé")
-- Montre       : quelle part du CA est faite par les premiers vendeurs.
-- Problème     : forte dépendance à quelques vendeurs (si 20 % des vendeurs
--                font 60-80 % du CA, perdre 1 gros vendeur = choc sur le CA).
-- Solution     : programme "key accounts" pour les gros vendeurs +
--                accompagnement des petits vendeurs pour diversifier.
WITH v AS (
    SELECT seller_id, SUM(total) AS ca
    FROM dwh.fact_orders
    WHERE dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
    GROUP BY seller_id
)
SELECT ROW_NUMBER() OVER (ORDER BY ca DESC)                                   AS "Rang vendeur",
       ROUND(100.0 * SUM(ca) OVER (ORDER BY ca DESC) / SUM(ca) OVER (), 1)     AS "% CA cumulé"
FROM v
ORDER BY 1;


-- A2 bis — Chiffre clé à afficher en "Nombre" : part du CA des 20 % meilleurs vendeurs
WITH v AS (
    SELECT seller_id, SUM(total) AS ca,
           NTILE(5) OVER (ORDER BY SUM(total) DESC) AS quintile
    FROM dwh.fact_orders
    WHERE dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
    GROUP BY seller_id
)
SELECT ROUND(100.0 * SUM(ca) FILTER (WHERE quintile = 1) / SUM(ca), 1)
       AS "% du CA fait par les 20 % meilleurs vendeurs"
FROM v;


-- A3 — Saisonnalité hebdomadaire : CA moyen par jour de la semaine
-- Visualisation : Barres
-- Montre       : les jours forts / faibles de la semaine.
-- Problème     : pics le week-end → risque de ruptures de stock et de
--                surcharge du service client ces jours-là.
-- Solution     : programmer les promotions en semaine pour lisser,
--                renforcer le support client le samedi/dimanche.
SELECT d.day_of_week                                    AS "N°",
       (ARRAY['Lundi','Mardi','Mercredi','Jeudi','Vendredi','Samedi','Dimanche'])[d.day_of_week]
                                                        AS "Jour",
       ROUND(AVG(j.ca), 0)                              AS "CA moyen (€)"
FROM (SELECT dt, SUM(total) AS ca FROM dwh.fact_orders GROUP BY dt) j
JOIN dwh.dim_date d ON d.dt = j.dt
GROUP BY d.day_of_week
ORDER BY d.day_of_week;


-- A4 — Poids des catégories dans le CA (30 jours) (US-04)
-- Visualisation : Camembert (Pie) ou Barres horizontales
-- Montre       : quelles catégories portent le business.
-- Problème     : une catégorie dominante = exposition à ses aléas
--                (saisonnalité, concurrence).
-- Solution     : recruter des vendeurs dans les catégories sous-représentées.
SELECT p.category                                         AS "Catégorie",
       ROUND(SUM(f.total), 0)                             AS "CA (€)",
       ROUND(100.0 * SUM(f.total) / SUM(SUM(f.total)) OVER (), 1) AS "Part du CA (%)"
FROM dwh.fact_orders f
JOIN dwh.dim_product p ON p.product_id = f.product_id
WHERE f.dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
GROUP BY p.category
ORDER BY "CA (€)" DESC;


-- A5 — Vendeurs en déclin : CA des 7 derniers jours vs 7 jours précédents
-- Visualisation : Tableau (trié par "Évolution (%)" croissante, rouge si < -30 %)
-- Montre       : les vendeurs dont les ventes chutent, avant qu'ils ne partent.
-- Problème     : un vendeur qui décroche puis devient inactif = CA et
--                commissions perdus, sans que personne ne s'en aperçoive.
-- Solution     : relance commerciale automatique des vendeurs à -30 % ou plus.
WITH ref AS (SELECT MAX(dt) AS m FROM dwh.fact_orders),
p AS (
    SELECT f.seller_id,
           SUM(f.total) FILTER (WHERE f.dt >  ref.m - 7)                       AS ca_7j,
           SUM(f.total) FILTER (WHERE f.dt <= ref.m - 7 AND f.dt > ref.m - 14) AS ca_7j_prec
    FROM dwh.fact_orders f, ref
    WHERE f.dt > ref.m - 14
    GROUP BY f.seller_id
)
SELECT s.name                                                        AS "Vendeur",
       ROUND(COALESCE(p.ca_7j_prec, 0), 0)                           AS "CA 7 j précédents (€)",
       ROUND(COALESCE(p.ca_7j, 0), 0)                                AS "CA 7 derniers jours (€)",
       ROUND(100.0 * (COALESCE(p.ca_7j, 0) - p.ca_7j_prec) / NULLIF(p.ca_7j_prec, 0), 1)
                                                                     AS "Évolution (%)"
FROM p
JOIN dwh.dim_seller s ON s.seller_id = p.seller_id
WHERE p.ca_7j_prec > 0
ORDER BY "Évolution (%)" ASC
LIMIT 15;


-- A6 — Catalogue dormant : produits jamais vendus sur 30 jours, par catégorie
-- Visualisation : Barres (ou Tableau)
-- Montre       : la part du catalogue qui ne génère aucune vente.
-- Problème     : catalogue "mort" qui pollue la recherche et l'expérience client.
-- Solution     : alerter les vendeurs (prix, photos, description) puis
--                désactiver les produits sans vente depuis 90 jours.
SELECT p.category                                                     AS "Catégorie",
       COUNT(*)                                                       AS "Produits au catalogue",
       COUNT(*) FILTER (WHERE v.product_id IS NULL)                   AS "Produits sans vente",
       ROUND(100.0 * COUNT(*) FILTER (WHERE v.product_id IS NULL) / COUNT(*), 1)
                                                                      AS "% dormant"
FROM dwh.dim_product p
LEFT JOIN (
    SELECT DISTINCT product_id
    FROM dwh.fact_orders
    WHERE dt > (SELECT MAX(dt) FROM dwh.fact_orders) - INTERVAL '30 days'
) v ON v.product_id = p.product_id
GROUP BY p.category
ORDER BY "% dormant" DESC;


-- A7 — Répartition des paniers par tranche de montant
-- Visualisation : Barres
-- Montre       : la distribution des montants de commande.
-- Problème     : beaucoup de petits paniers = frais logistiques élevés
--                par rapport à la commission de 12 %.
-- Solution     : seuil de livraison gratuite / ventes additionnelles
--                pour faire monter le panier moyen.
WITH c AS (
    SELECT order_id, SUM(total) AS panier
    FROM dwh.fact_orders
    GROUP BY order_id
)
SELECT CASE
         WHEN panier < 20  THEN '1. Moins de 20 €'
         WHEN panier < 50  THEN '2. 20 à 50 €'
         WHEN panier < 100 THEN '3. 50 à 100 €'
         WHEN panier < 150 THEN '4. 100 à 150 €'
         ELSE                   '5. 150 € et plus'
       END                     AS "Tranche de panier",
       COUNT(*)                AS "Nombre de commandes"
FROM c
GROUP BY 1
ORDER BY 1;


-- =====================================================================
-- PARTIE B — QUALITÉ DES DONNÉES (contrôles automatiques)
-- Visualisation conseillée : Tableau, avec "Statut" en rouge si KO.
-- Lien avec le cahier des charges : DataQualityOperator (bonus Should)
-- =====================================================================

-- B1 — Tableau de bord qualité : un contrôle par ligne
-- Problème     : des données fausses = des KPI faux = de mauvaises décisions
--                (et une facturation des commissions erronée).
-- Solution     : exécuter ces contrôles dans Airflow AVANT le chargement DWH
--                (branche "alerte" si un contrôle est KO).
WITH ref AS (SELECT MAX(dt) AS m, MIN(dt) AS mi FROM dwh.fact_orders),
checks AS (
    SELECT 1 AS ordre, 'Montants nuls ou négatifs' AS controle,
           COUNT(*) AS anomalies
    FROM dwh.fact_orders WHERE total IS NULL OR total <= 0
  UNION ALL
    SELECT 2, 'Quantités nulles ou négatives',
           COUNT(*) FROM dwh.fact_orders WHERE quantity IS NULL OR quantity <= 0
  UNION ALL
    SELECT 3, 'Commandes datées dans le futur',
           COUNT(*) FROM dwh.fact_orders WHERE dt > CURRENT_DATE
  UNION ALL
    SELECT 4, 'Commission différente de 12 % (écart > 1 cent)',
           COUNT(*) FROM dwh.fact_orders WHERE ABS(commission - ROUND(total * 0.12, 2)) > 0.01
  UNION ALL
    SELECT 5, 'Vendeur de la commande ≠ vendeur du produit',
           COUNT(*) FROM dwh.fact_orders f
           JOIN dwh.dim_product p ON p.product_id = f.product_id
           WHERE f.seller_id <> p.seller_id
  UNION ALL
    SELECT 6, 'Jours sans aucune donnée (trous dans la période)',
           COUNT(*) FROM dwh.dim_date d, ref
           WHERE d.dt BETWEEN ref.mi AND ref.m
             AND NOT EXISTS (SELECT 1 FROM dwh.fact_orders f WHERE f.dt = d.dt)
  UNION ALL
    SELECT 7, 'Vendeurs sans nom ou sans pays',
           COUNT(*) FROM dwh.dim_seller WHERE name IS NULL OR name = '' OR country IS NULL
  UNION ALL
    SELECT 8, 'Produits sans catégorie',
           COUNT(*) FROM dwh.dim_product WHERE category IS NULL OR category = ''
  UNION ALL
    SELECT 9, 'Valeurs aberrantes (ligne > 10 × le montant moyen)',
           COUNT(*) FROM dwh.fact_orders
           WHERE total > 10 * (SELECT AVG(total) FROM dwh.fact_orders)
)
SELECT controle                                AS "Contrôle",
       anomalies                               AS "Lignes en anomalie",
       CASE WHEN anomalies = 0 THEN 'OK' ELSE 'KO' END AS "Statut"
FROM checks
ORDER BY ordre;


-- B2 — Fraîcheur des données : le pipeline a-t-il tourné ?
-- Visualisation : Nombre (ou Tableau)
-- Problème     : si le DAG échoue, le dashboard affiche des chiffres périmés
--                sans que personne ne le remarque.
-- Solution     : afficher la date de dernière donnée en haut du dashboard
--                + alerte si le retard dépasse 1 jour (US-07).
SELECT MAX(dt)                     AS "Dernière date chargée",
       CURRENT_DATE - MAX(dt)      AS "Retard (jours)",
       COUNT(DISTINCT dt)          AS "Jours disponibles"
FROM dwh.fact_orders;


-- B3 — Volume chargé par jour (détecter un chargement partiel)
-- Visualisation : Barres (X = Date, Y = Lignes chargées)
-- Problème     : un jour avec beaucoup moins de lignes peut être une vraie
--                baisse de ventes… ou un chargement API incomplet.
-- Solution     : comparer avec le nombre de commandes renvoyé par l'API
--                (contrôle de complétude dans le DAG) avant de publier.
SELECT dt                          AS "Date",
       COUNT(*)                    AS "Lignes chargées",
       COUNT(DISTINCT order_id)    AS "Commandes distinctes"
FROM dwh.fact_orders
GROUP BY dt
ORDER BY dt;
