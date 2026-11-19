"""
Archivage MinIO et chargement PostgreSQL de la Marketplace.

Fonctions disponibles :
- upload_raw() : archiver une réponse JSON dans MinIO.
- read_raw() : relire une archive JSON depuis MinIO.
- load_sellers() : insérer ou mettre à jour les vendeurs.
- load_products() : insérer ou mettre à jour les produits.
- load_orders() : remplacer les commandes d'une journée.

Les appels HTTP restent dans api_hook.py.

Connections Airflow nécessaires :
- minio_s3
- postgres_dwh
"""

import json
from datetime import date
from decimal import Decimal, InvalidOperation

from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook


# Paramètres communs aux fonctions.
MINIO_CONN_ID = "minio_s3"
POSTGRES_CONN_ID = "postgres_dwh"
RAW_BUCKET = "data-lake"

ALLOWED_ENTITIES = {
    "orders",
    "sellers",
    "products",
    "test_orders",
}


def _parse_date(value):
    """
    Vérifier une date au format YYYY-MM-DD.

    Retour :
        Objet Python date.

    Cette fonction ne contacte aucun service.
    """

    if not isinstance(value, str):
        raise TypeError("La date doit être une chaîne YYYY-MM-DD.")

    parsed_date = date.fromisoformat(value)

    if parsed_date.isoformat() != value:
        raise ValueError("La date doit respecter le format YYYY-MM-DD.")

    return parsed_date


def _raw_key(entity, requested_date):
    """
    Construire le chemin d'un objet MinIO.

    Exemple :
        raw/orders/dt=2026-04-07/data.json
    """

    _parse_date(requested_date)

    if entity not in ALLOWED_ENTITIES:
        raise ValueError(f"Entité non autorisée : {entity}")

    return f"raw/{entity}/dt={requested_date}/data.json"


def _validate_records(records, required_fields, entity):
    """
    Vérifier la structure d'une liste de données avant son chargement.

    Chaque élément doit être un dictionnaire contenant les champs requis.
    Les valeurs requises ne doivent pas être None.

    Les champs supplémentaires sont acceptés et seront ignorés par le SQL.
    """

    if not isinstance(records, list):
        raise TypeError(
            f"{entity} : une liste de dictionnaires est attendue."
        )

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise TypeError(
                f"{entity} : l'élément {index} n'est pas un dictionnaire."
            )

        missing_fields = [
            field
            for field in required_fields
            if field not in record or record[field] is None
        ]

        if missing_fields:
            raise ValueError(
                f"{entity} : champs absents ou nuls à l'élément "
                f"{index} : {', '.join(missing_fields)}"
            )


def _execute_transaction(action):
    """
    Exécuter une opération SQL dans une transaction.

    Paramètre :
        action : fonction recevant un curseur PostgreSQL.

    Si toutes les requêtes réussissent :
        commit() valide les modifications.

    En cas d'erreur :
        rollback() annule toutes les modifications de la transaction.

    La connexion est toujours fermée à la fin.
    """

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    connection = hook.get_conn()

    try:
        connection.autocommit = False

        with connection.cursor() as cursor:
            result = action(cursor)

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def upload_raw(entity, requested_date, payload):
    """
    Archiver une réponse JSON dans MinIO.

    Paramètres :
        entity : "orders", "sellers", "products" ou "test_orders".
        requested_date : date de traitement au format YYYY-MM-DD.
        payload : liste ou dictionnaire Python à sauvegarder.

    Retour :
        Adresse logique de l'objet sauvegardé.

    Un rejeu remplace l'objet au même chemin.
    """

    object_key = _raw_key(entity, requested_date)

    if not isinstance(payload, (list, dict)):
        raise TypeError("payload doit être une liste ou un dictionnaire.")

    # Préparer le JSON avant de contacter MinIO.
    json_content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )

    # Créer le Hook seulement lorsque la fonction est appelée.
    hook = S3Hook(aws_conn_id=MINIO_CONN_ID)

    hook.load_string(
        string_data=json_content,
        key=object_key,
        bucket_name=RAW_BUCKET,
        replace=True,
        encoding="utf-8",
    )

    return f"s3://{RAW_BUCKET}/{object_key}"


def read_raw(entity, requested_date):
    """
    Relire une archive JSON depuis MinIO.

    Paramètres :
        entity : nom de l'entité archivée.
        requested_date : date de l'archive au format YYYY-MM-DD.

    Retour :
        Liste ou dictionnaire Python.

    Cette fonction permet de charger PostgreSQL depuis l'archive,
    sans rappeler l'API.
    """

    object_key = _raw_key(entity, requested_date)
    hook = S3Hook(aws_conn_id=MINIO_CONN_ID)

    json_content = hook.read_key(
        key=object_key,
        bucket_name=RAW_BUCKET,
    )

    payload = json.loads(json_content)

    if not isinstance(payload, (list, dict)):
        raise ValueError(
            "L'archive doit contenir une liste ou un objet JSON."
        )

    return payload


def load_sellers(sellers):
    """
    Insérer ou mettre à jour les vendeurs dans dwh.dim_seller.

    Champs attendus :
        seller_id, name, country, joined_date.

    Retour :
        Nombre de vendeurs traités.

    Un vendeur existant est mis à jour, pas dupliqué.
    """

    required_fields = (
        "seller_id",
        "name",
        "country",
        "joined_date",
    )

    _validate_records(sellers, required_fields, "sellers")

    # Préparer toutes les lignes avant de modifier PostgreSQL.
    rows = [
        (
            seller["seller_id"],
            seller["name"],
            seller["country"],
            _parse_date(seller["joined_date"]),
        )
        for seller in sellers
    ]

    sql = """
        INSERT INTO dwh.dim_seller (
            seller_id,
            name,
            country,
            joined_date
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (seller_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            country = EXCLUDED.country,
            joined_date = EXCLUDED.joined_date;
    """

    def action(cursor):
        if rows:
            cursor.executemany(sql, rows)

        return len(rows)

    return _execute_transaction(action)


def load_products(products):
    """
    Insérer ou mettre à jour les produits dans dwh.dim_product.

    Champs attendus :
        product_id, name, category, seller_id.

    Prérequis :
        Charger les vendeurs avant les produits.

    Retour :
        Nombre de produits traités.

    Le champ price de l'API n'est pas inséré dans cette dimension.
    """

    required_fields = (
        "product_id",
        "name",
        "category",
        "seller_id",
    )

    _validate_records(products, required_fields, "products")

    rows = [
        (
            product["product_id"],
            product["name"],
            product["category"],
            product["seller_id"],
        )
        for product in products
    ]

    sql = """
        INSERT INTO dwh.dim_product (
            product_id,
            name,
            category,
            seller_id
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (product_id)
        DO UPDATE SET
            name = EXCLUDED.name,
            category = EXCLUDED.category,
            seller_id = EXCLUDED.seller_id;
    """

    def action(cursor):
        if rows:
            cursor.executemany(sql, rows)

        return len(rows)

    return _execute_transaction(action)


def load_orders(requested_date, orders):
    """
    Remplacer les commandes d'une journée dans staging.orders.

    Paramètres :
        requested_date : date à charger au format YYYY-MM-DD.
        orders : liste des commandes à insérer.

    Champs attendus :
        order_id, dt, seller_id, product_id, quantity, unit_price.

    Retour :
        Nombre de commandes chargées.

    Sécurité :
        Toutes les données sont préparées avant la suppression.
        Le DELETE et les INSERT utilisent la même transaction.
        Une liste vide est refusée pour éviter un effacement accidentel.

    Le total et la commission sont calculés ensuite par Lydia.
    loaded_at est rempli automatiquement par PostgreSQL.
    """

    target_date = _parse_date(requested_date)

    required_fields = (
        "order_id",
        "dt",
        "seller_id",
        "product_id",
        "quantity",
        "unit_price",
    )

    _validate_records(orders, required_fields, "orders")

    if not orders:
        raise ValueError(
            "Aucune commande reçue : chargement annulé "
            "pour préserver les données existantes."
        )

    rows = []
    seen_order_ids = set()

    # Valider toutes les commandes avant de modifier la base.
    for order in orders:
        order_id = order["order_id"]
        order_date = _parse_date(order["dt"])

        if order_date != target_date:
            raise ValueError(
                f"La commande {order_id} n'appartient pas "
                f"au {requested_date}."
            )

        if order_id in seen_order_ids:
            raise ValueError(
                f"Identifiant de commande dupliqué : {order_id}"
            )

        seen_order_ids.add(order_id)

        quantity = order["quantity"]

        if type(quantity) is not int or quantity <= 0:
            raise ValueError(
                f"Quantité invalide pour la commande {order_id}."
            )

        try:
            unit_price = Decimal(str(order["unit_price"]))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                f"Prix invalide pour la commande {order_id}."
            ) from exc

        if not unit_price.is_finite() or unit_price < 0:
            raise ValueError(
                f"Prix invalide pour la commande {order_id}."
            )

        rows.append(
            (
                order_id,
                target_date,
                order["seller_id"],
                order["product_id"],
                quantity,
                unit_price,
            )
        )

    insert_sql = """
        INSERT INTO staging.orders (
            order_id,
            dt,
            seller_id,
            product_id,
            quantity,
            unit_price
        )
        VALUES (%s, %s, %s, %s, %s, %s);
    """

    def action(cursor):
        # Ne supprimer que la journée que l'on recharge.
        cursor.execute(
            "DELETE FROM staging.orders WHERE dt = %s",
            (target_date,),
        )

        # Si une insertion échoue, la suppression sera aussi annulée.
        cursor.executemany(insert_sql, rows)

        return len(rows)

    return _execute_transaction(action)