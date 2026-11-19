"""Fixtures partagées pour les tests pytest.

Lancement : docker compose exec airflow-worker pytest tests/ -v
"""
import os
import sys

import pytest

# Rendre les plugins (hooks/operators custom) importables hors du scheduler
PLUGINS_DIR = os.environ.get("AIRFLOW_PLUGINS_DIR", "/opt/airflow/plugins")
if PLUGINS_DIR not in sys.path:
    sys.path.insert(0, PLUGINS_DIR)

DAGS_FOLDER = os.environ.get("AIRFLOW_DAGS_DIR", "/opt/airflow/dags")


def _load_dagbag_class():
    # Airflow 3.x : DagBag a été déplacé ; on garde un fallback pour compatibilité
    try:
        from airflow.dag_processing.dagbag import DagBag  # type: ignore
    except ImportError:
        from airflow.models.dagbag import DagBag  # type: ignore
    return DagBag


@pytest.fixture(scope="session")
def dagbag():
    DagBag = _load_dagbag_class()
    return DagBag(dag_folder=DAGS_FOLDER, include_examples=False)
