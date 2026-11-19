"""
API Marketplace simulée (Maelys Marketplace).

Recréée d'après la partie 5 du cahier des charges, faute de kit fourni :
- GET /health                       -> {status, version}        (sans auth)
- GET /orders?date=YYYY-MM-DD       -> liste de commandes       (auth Bearer)
- GET /sellers?limit=N              -> liste de vendeurs        (auth Bearer)
- GET /products                     -> catalogue                (auth Bearer)
- GET /customers?limit=N            -> liste de clients         (auth Bearer)

Déterministe : seed = md5(date). Une même date renvoie toujours
exactement les mêmes commandes (nécessaire pour tester l'idempotence).
"""

import hashlib
import os
import random
from datetime import date, timedelta

from flask import Flask, jsonify, request

app = Flask(__name__)

API_VERSION = "1.0.0"
API_TOKEN = os.environ.get("API_TOKEN", "formation-token-2026")

# Taille du catalogue (le cahier parle de 2 400 vendeurs et 180 000 produits ;
# le nombre de produits est réduit par défaut pour garder des réponses légères).
N_SELLERS = int(os.environ.get("N_SELLERS", 2400))
N_PRODUCTS = int(os.environ.get("N_PRODUCTS", 18000))
N_CUSTOMERS = int(os.environ.get("N_CUSTOMERS", 50000))
ORDERS_PER_DAY = int(os.environ.get("ORDERS_PER_DAY", 8500))

CATEGORIES = [
    "Maison", "Cuisine", "Mode", "Beauté", "Bijoux",
    "Jouets", "Sport", "Papeterie", "Épicerie fine", "Déco",
]
COUNTRIES = ["France", "France", "France", "Belgique", "Suisse", "Espagne", "Italie"]
# Fourchettes de prix calées sur le cahier des charges :
# ~8 500 commandes/jour et ~4,2 M€/mois, soit un panier moyen d'environ 16 €.
PRICE_RANGES = {
    "Maison": (4, 18), "Cuisine": (3, 14), "Mode": (5, 26),
    "Beauté": (2, 11), "Bijoux": (6, 34), "Jouets": (3, 14),
    "Sport": (4, 26), "Papeterie": (1, 6), "Épicerie fine": (2, 10),
    "Déco": (3, 20),
}


def seeded_random(key: str) -> random.Random:
    """Générateur aléatoire reproductible : même clé -> mêmes nombres."""
    seed = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)
    return random.Random(seed)


# ---------------------------------------------------------------------------
# Catalogue fixe (identique à chaque démarrage)
# ---------------------------------------------------------------------------
def build_sellers():
    rng = seeded_random("sellers")
    sellers = []
    for i in range(1, N_SELLERS + 1):
        joined = date(2020, 1, 1) + timedelta(days=rng.randint(0, 6 * 365))
        sellers.append({
            "seller_id": i,
            "name": f"Vendeur {i:04d}",
            "country": rng.choice(COUNTRIES),
            "joined_date": joined.isoformat(),
        })
    return sellers


def build_products():
    rng = seeded_random("products")
    products = []
    for i in range(1, N_PRODUCTS + 1):
        category = rng.choice(CATEGORIES)
        low, high = PRICE_RANGES[category]
        products.append({
            "product_id": i,
            "name": f"{category} - article {i:06d}",
            "category": category,
            "seller_id": rng.randint(1, N_SELLERS),
            "price": round(rng.uniform(low, high), 2),
        })
    return products


def build_customers():
    rng = seeded_random("customers")
    return [
        {
            "customer_id": i,
            "name": f"Client {i:06d}",
            "country": rng.choice(COUNTRIES),
        }
        for i in range(1, N_CUSTOMERS + 1)
    ]


SELLERS = build_sellers()
PRODUCTS = build_products()
CUSTOMERS = build_customers()


# ---------------------------------------------------------------------------
# Authentification Bearer
# ---------------------------------------------------------------------------
@app.before_request
def check_token():
    if request.path == "/health":
        return None
    if request.headers.get("Authorization", "") != f"Bearer {API_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401
    return None


def read_limit(default: int, maximum: int) -> int:
    try:
        value = int(request.args.get("limit", default))
    except ValueError:
        return default
    return max(1, min(value, maximum))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return jsonify({"status": "ok", "version": API_VERSION})


@app.get("/orders")
def orders():
    raw_date = request.args.get("date")
    if not raw_date:
        return jsonify({"error": "Paramètre 'date' obligatoire (YYYY-MM-DD)"}), 400
    try:
        day = date.fromisoformat(raw_date)
    except ValueError:
        return jsonify({"error": "Format de date invalide, attendu YYYY-MM-DD"}), 400

    rng = seeded_random(day.isoformat())   # seed = md5(date)

    # Volume du jour : ~8 500 commandes, un peu plus le week-end,
    # et de temps en temps une journée creuse (utile pour la détection d'anomalies).
    volume = ORDERS_PER_DAY * rng.uniform(0.85, 1.15)
    if day.isoweekday() >= 6:
        volume *= 1.2
    if rng.random() < 0.07:
        volume *= 0.5
    n_orders = int(volume)

    # Identifiant unique par jour, qui tient dans un INTEGER PostgreSQL
    base_id = (day - date(2020, 1, 1)).days * 100000
    result = []
    for n in range(1, n_orders + 1):
        product = PRODUCTS[rng.randrange(N_PRODUCTS)]
        result.append({
            "order_id": base_id + n,
            "dt": day.isoformat(),
            "customer_id": rng.randint(1, N_CUSTOMERS),
            "seller_id": product["seller_id"],
            "product_id": product["product_id"],
            "quantity": rng.choices([1, 2, 3, 4, 5], weights=[60, 22, 10, 5, 3])[0],
            "unit_price": product["price"],
        })
    return jsonify(result)


@app.get("/sellers")
def sellers():
    return jsonify(SELLERS[: read_limit(N_SELLERS, N_SELLERS)])


@app.get("/products")
def products():
    return jsonify(PRODUCTS)


@app.get("/customers")
def customers():
    return jsonify(CUSTOMERS[: read_limit(1000, N_CUSTOMERS)])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)