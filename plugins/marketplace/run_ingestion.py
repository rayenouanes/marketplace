"""
Lancement manuel de l'ingestion Marketplace.

Parcours :
API → MinIO → PostgreSQL.

Ce fichier ne lance pas les transformations DWH de Lydia.
"""

import argparse

from airflow.providers.postgres.hooks.postgres import PostgresHook

from marketplace.api_hook import MarketplaceAPIHook
from marketplace.ingestion import (
    upload_raw,
    read_raw,
    load_sellers,
    load_products,
    load_orders,
)


def check_database():
    """
    Vérifier la connexion PostgreSQL et la présence des tables.

    Cette fonction ne modifie aucune donnée.
    """

    hook = PostgresHook(postgres_conn_id="postgres_dwh")
    connection = hook.get_conn()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    current_database(),
                    to_regclass('dwh.dim_seller'),
                    to_regclass('dwh.dim_product'),
                    to_regclass('staging.orders');
                """
            )

            database, sellers_table, products_table, orders_table = (
                cursor.fetchone()
            )

        missing = []

        if sellers_table is None:
            missing.append("dwh.dim_seller")

        if products_table is None:
            missing.append("dwh.dim_product")

        if orders_table is None:
            missing.append("staging.orders")

        if missing:
            raise RuntimeError(
                "Tables absentes dans la base "
                f"{database} : {', '.join(missing)}. "
                "Le schéma SQL de Lydia doit être appliqué."
            )

        print(f"OK : connexion PostgreSQL et tables présentes dans {database}.")

    finally:
        connection.close()


def run_ingestion(requested_date):
    """
    Archiver les données, puis charger les dimensions et le staging.

    Les archives sont toutes écrites avant les chargements PostgreSQL.
    Chaque fonction de chargement possède sa propre transaction :
    ce programme n'est pas une transaction globale.
    """

    # Vérifier l'accès aux tables avant de commencer l'ingestion.
    check_database()

    api = MarketplaceAPIHook()

    # Récupérer les réponses de l'API.
    print("Récupération des vendeurs...")
    sellers = api.get_sellers()

    print("Récupération des produits...")
    products = api.get_products()

    print(f"Récupération des commandes du {requested_date}...")
    orders = api.get_orders(requested_date)

    # Archiver les réponses originales dans MinIO.
    for entity, payload in (
        ("sellers", sellers),
        ("products", products),
        ("orders", orders),
    ):
        location = upload_raw(entity, requested_date, payload)
        print(f"Archive enregistrée : {location}")

    # Relire les archives pour alimenter PostgreSQL.
    # Les vendeurs sont chargés avant les produits.
    sellers_count = load_sellers(
        read_raw("sellers", requested_date)
    )
    print(f"Vendeurs traités : {sellers_count}")

    products_count = load_products(
        read_raw("products", requested_date)
    )
    print(f"Produits traités : {products_count}")

    orders_count = load_orders(
        requested_date,
        read_raw("orders", requested_date),
    )
    print(f"Commandes chargées dans staging.orders : {orders_count}")

    print("Ingestion terminée.")
    print("Les transformations DWH de Lydia restent à exécuter ensuite.")


def main():
    """Lire la date fournie dans la commande et lancer l'ingestion."""

    parser = argparse.ArgumentParser(
        description="Ingestion Marketplace : API → MinIO → PostgreSQL."
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Date des commandes au format YYYY-MM-DD.",
    )

    args = parser.parse_args()
    run_ingestion(args.date)


if __name__ == "__main__":
    main()