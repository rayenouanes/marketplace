#Les fonctions d’archivage MinIO et de chargement staging
#Les fonctions pour sauvegarder les JSON dans MinIO et charger les tables

"""
Ce fichier contiendra les fonctions permettant de :
1. Sauvegarder les données JSON de l'API dans MinIO.
2. Charger les vendeurs dans PostgreSQL.
3. Charger les produits dans PostgreSQL.
4. Charger les commandes dans PostgreSQL.

Les appels HTTP sont gérés séparément dans api_hook.py.
"""


import json
from datetime import date
# 1. Charger l'outil dans le programme.
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

# 2. Préparer un Hook utilisant les paramètres de minio_s3.
hook = S3Hook(aws_conn_id="minio_s3")

def upload_raw(entity, requested_date, payload):
    """
    Archiver des données JSON dans MinIO.

    Paramètres :
        entity : nom des données, par exemple "orders".
        requested_date : date au format "YYYY-MM-DD".
        payload : liste ou dictionnaire Python à sauvegarder.

    Retour :
        Chemin de l'objet créé dans MinIO.
    """

    # Vérifier que la date respecte le format attendu.
    parsed_date = date.fromisoformat(requested_date)

    if parsed_date.isoformat() != requested_date:
        raise ValueError("La date doit respecter le format YYYY-MM-DD.")

    # Limiter les noms autorisés pour éviter les chemins inattendus.
    allowed_entities = {"orders", "sellers", "products", "test_orders"}

    if entity not in allowed_entities:
        raise ValueError(f"Entité non autorisée : {entity}")

    # Les réponses attendues sont des listes ou des objets JSON.
    if not isinstance(payload, (list, dict)):
        raise TypeError("payload doit être une liste ou un dictionnaire.")

    # Définir le bucket et le chemin du fichier.
    bucket_name = "data-lake"
    object_key = f"raw/{entity}/dt={requested_date}/data.json"

    # Transformer les données Python en texte JSON.
    json_content = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )

    # Utiliser la Connection Airflow déjà vérifiée.
    hook = S3Hook(aws_conn_id="minio_s3")

    # Envoyer le JSON dans MinIO.
    # Si le fichier existe déjà à ce chemin, il sera remplacé.
    hook.load_string(
        string_data=json_content,
        key=object_key,
        bucket_name=bucket_name,
        replace=True,
        encoding="utf-8",
    )

    # Retourner l'emplacement du fichier pour les logs.
    return f"s3://{bucket_name}/{object_key}"


def load_sellers(sellers):
    """
    Charger les vendeurs dans la table dwh.dim_seller.

    Paramètres :
        sellers (list[dict]) :
            Liste de vendeurs contenant les champs convenus :
            seller_id, name, country et joined_date.

    Comportement prévu :
        - Insérer les vendeurs qui n'existent pas.
        - Mettre à jour ceux qui existent déjà.
        - Utiliser seller_id pour identifier chaque vendeur.
    """

    # Étape 1 : vérifier que les vendeurs possèdent les champs attendus.

    # Étape 2 : préparer les valeurs à transmettre à PostgreSQL.

    # Étape 3 : récupérer la connexion PostgreSQL DWH depuis Airflow.

    # Étape 4 : exécuter l'INSERT avec ON CONFLICT (seller_id) DO UPDATE.

    # Étape 5 : valider la transaction si tout réussit.
    # En cas d'erreur, annuler la transaction.

    raise NotImplementedError("Chargement vendeurs à implémenter")


def load_products(products):
    """
    Charger les produits dans la table dwh.dim_product.

    Paramètres :
        products (list[dict]) :
            Liste de produits contenant les champs convenus :
            product_id, name, category et seller_id.

    Comportement prévu :
        - Insérer les produits qui n'existent pas.
        - Mettre à jour ceux qui existent déjà.
        - Utiliser product_id pour identifier chaque produit.

    Prérequis :
        Les vendeurs référencés doivent être chargés avant les produits.
    """

    # Étape 1 : vérifier que les produits possèdent les champs attendus.

    # Étape 2 : préparer les valeurs à transmettre à PostgreSQL.

    # Étape 3 : récupérer la connexion PostgreSQL DWH depuis Airflow.

    # Étape 4 : exécuter l'INSERT avec ON CONFLICT (product_id) DO UPDATE.

    # Étape 5 : valider la transaction si tout réussit.
    # En cas d'erreur, annuler la transaction.

    raise NotImplementedError("Chargement produits à implémenter")


def load_orders(requested_date, orders):
    """
    Remplacer les commandes d'une journée dans staging.orders.

    Paramètres :
        requested_date (str) :
            Date à charger au format "YYYY-MM-DD".

        orders (list[dict]) :
            Liste de commandes contenant les champs convenus :
            order_id, dt, seller_id, product_id, quantity et unit_price.

    Comportement prévu :
        - Vérifier les données avant toute suppression.
        - Supprimer les anciennes commandes de la date demandée.
        - Insérer les commandes reçues pour cette date.
        - Effectuer la suppression et les insertions dans une seule
          transaction.

    Important :
        Le total et la commission seront calculés par le SQL de Lydia.
        loaded_at est rempli automatiquement par PostgreSQL.
    """

    # Étape 1 : vérifier le format de requested_date.

    # Étape 2 : vérifier les champs de chaque commande et s'assurer
    # que leur date correspond à requested_date.

    # Étape 3 : préparer toutes les lignes avant de modifier la base.

    # Étape 4 : récupérer la connexion PostgreSQL DWH depuis Airflow.

    # Étape 5 : supprimer uniquement les commandes de requested_date.

    # Étape 6 : insérer les nouvelles commandes avec des paramètres SQL.

    # Étape 7 : valider le DELETE et les INSERT ensemble.
    # En cas d'erreur, tout annuler pour conserver les anciennes données.

    raise NotImplementedError("Chargement commandes à implémenter")