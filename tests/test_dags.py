"""Tests pytest du pipeline Marketplace (cahier des charges §12.2).

Lancement :
    docker compose exec airflow-worker pytest tests/ -v
"""
import os
import pathlib
import re

import pytest

INGEST_DAG_ID = "marketplace_orders_ingest_daily"

AIRFLOW_HOME = pathlib.Path(os.environ.get("AIRFLOW_HOME", "/opt/airflow"))
SQL_DIR = pathlib.Path(os.environ.get("MARKETPLACE_SQL_DIR", AIRFLOW_HOME / "sql"))
PLUGINS_DIR = pathlib.Path(os.environ.get("AIRFLOW_PLUGINS_DIR", AIRFLOW_HOME / "plugins"))


# ---------------------------------------------------------------------------
# 1. Les DAGs se chargent sans erreur
# ---------------------------------------------------------------------------
def test_no_import_errors(dagbag):
    assert dagbag.import_errors == {}, f"Erreurs d'import : {dagbag.import_errors}"


# ---------------------------------------------------------------------------
# 2. Aucun DAG ne rejoue tout l'historique au démarrage
# ---------------------------------------------------------------------------
def test_all_dags_catchup_false(dagbag):
    fautifs = [dag_id for dag_id, dag in dagbag.dags.items() if dag.catchup]
    assert not fautifs, f"DAGs avec catchup=True : {fautifs}"


# ---------------------------------------------------------------------------
# 3. Le DAG principal existe et est planifié chaque jour
# ---------------------------------------------------------------------------
def test_marketplace_ingest_dag_present(dagbag):
    dag = dagbag.dags.get(INGEST_DAG_ID)  # lecture directe, sans base Airflow
    assert dag is not None, f"DAG {INGEST_DAG_ID} introuvable"
    assert str(dag.schedule) == "@daily" or "daily" in str(dag.timetable).lower()


# ---------------------------------------------------------------------------
# 4. La transformation staging -> dwh est idempotente (DELETE + INSERT par date)
# ---------------------------------------------------------------------------
def _check_idempotent_sql(path, table):
    assert path.exists(), f"Fichier introuvable : {path}"
    sql = path.read_text(encoding="utf-8")
    delete = re.search(rf"DELETE\s+FROM\s+{re.escape(table)}\s+WHERE\s+dt\s*=\s*'\{{\{{\s*ds\s*\}}\}}'",
                       sql, re.I)
    insert = re.search(rf"INSERT\s+INTO\s+{re.escape(table)}", sql, re.I)
    assert delete, f"{path.name} : il manque DELETE FROM {table} WHERE dt = '{{{{ ds }}}}'"
    assert insert, f"{path.name} : il manque INSERT INTO {table}"
    assert delete.start() < insert.start(), f"{path.name} : le DELETE doit venir avant l'INSERT"
    assert re.search(r"\bBEGIN\b", sql, re.I) and re.search(r"\bCOMMIT\b", sql, re.I), \
        f"{path.name} : DELETE et INSERT doivent être dans une transaction"


def test_marketplace_ingest_has_idempotent_transform():
    _check_idempotent_sql(SQL_DIR / "transform_fact_orders.sql", "dwh.fact_orders")


def test_analytics_summary_is_idempotent():
    _check_idempotent_sql(SQL_DIR / "analytics_daily_summary.sql", "analytics.daily_summary")


# ---------------------------------------------------------------------------
# 5. Aucun token API écrit en dur dans le code (§15.3)
# ---------------------------------------------------------------------------
def test_no_hardcoded_token(dagbag):
    dossiers = [pathlib.Path(dagbag.dag_folder), PLUGINS_DIR]
    for dossier in dossiers:
        for fichier in dossier.rglob("*.py"):
            assert "formation-token-2026" not in fichier.read_text(encoding="utf-8"), (
                f"Token en dur détecté dans {fichier}"
            )
