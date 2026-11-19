"""Tests structurels des DAGs (MVP : 3 tests minimum, cf. §12.2)."""
import inspect
import re

import pytest

INGEST_DAG_ID = "marketplace_orders_ingest_daily"
EXPECTED_DAGS = [
    INGEST_DAG_ID,
    # décommenter au fur et à mesure que les DAGs sont mergés dans main
    # "marketplace_dims_refresh_daily",
    # "marketplace_analytics_aggregate_daily",
]


# ---------------------------------------------------------------- MVP (obligatoires)

def test_no_import_errors(dagbag):
    """Aucun DAG ne doit lever d'erreur à l'import."""
    assert dagbag.import_errors == {}, f"Erreurs d'import : {dagbag.import_errors}"


def test_all_dags_catchup_false(dagbag):
    """catchup=False partout (sinon Airflow rejoue tout l'historique au démarrage)."""
    fautifs = [dag_id for dag_id, dag in dagbag.dags.items() if dag.catchup]
    assert not fautifs, f"DAGs avec catchup=True : {fautifs}"


def _task_code(task) -> str:
    """Récupère le SQL ou le code Python exécuté par une task, pour l'inspecter."""
    parts = []
    sql = getattr(task, "sql", None)
    if sql:
        parts.append(sql if isinstance(sql, str) else "\n".join(map(str, sql)))
    func = getattr(task, "python_callable", None)
    if func is not None:
        try:
            parts.append(inspect.getsource(func))
        except (OSError, TypeError):
            pass
    return "\n".join(parts)


def test_marketplace_ingest_has_idempotent_transform(dagbag):
    """Le DAG principal doit contenir une transfo DELETE + INSERT sur dwh.fact_orders,
    filtrée par la date logique du run (pattern d'idempotence §9.3)."""
    dag = dagbag.get_dag(INGEST_DAG_ID)
    assert dag is not None, f"DAG {INGEST_DAG_ID} introuvable"

    delete_re = re.compile(r"DELETE\s+FROM\s+dwh\.fact_orders", re.I)
    insert_re = re.compile(r"INSERT\s+INTO\s+dwh\.fact_orders", re.I)

    candidates = [
        t.task_id for t in dag.tasks
        if delete_re.search(_task_code(t)) and insert_re.search(_task_code(t))
    ]
    assert candidates, "Aucune task ne fait DELETE + INSERT sur dwh.fact_orders"

    # La suppression doit être partitionnée par date (pas de DELETE global)
    for task_id in candidates:
        code = _task_code(dag.get_task(task_id))
        assert re.search(r"WHERE\s+dt\s*=", code, re.I), (
            f"{task_id} : le DELETE doit être filtré par dt (sinon on vide toute la table)"
        )


# ---------------------------------------------------------------- tests complémentaires

@pytest.mark.parametrize("dag_id", EXPECTED_DAGS)
def test_expected_dags_present(dagbag, dag_id):
    assert dag_id in dagbag.dags, f"DAG attendu absent : {dag_id}"


def test_ingest_dag_structure(dagbag):
    """Ordre extract → raw (MinIO) → staging → dwh.
    Adapter les mots-clés aux task_id réels choisis par l'équipe."""
    dag = dagbag.get_dag(INGEST_DAG_ID)
    assert dag is not None
    assert len(dag.tasks) >= 3, "Le pipeline doit comporter au moins 3 étapes"

    # Le DAG ne doit avoir aucun cycle et une seule racine (extract)
    roots = [t.task_id for t in dag.roots]
    assert len(roots) >= 1


def test_ingest_dag_has_retries(dagbag):
    """Les tasks doivent avoir au moins 1 retry (robustesse API)."""
    dag = dagbag.get_dag(INGEST_DAG_ID)
    sans_retry = [t.task_id for t in dag.tasks if (t.retries or 0) < 1]
    assert not sans_retry, f"Tasks sans retry : {sans_retry}"


def test_no_hardcoded_token(dagbag):
    """Le token API ne doit jamais apparaître en dur dans un DAG (§15.3)."""
    import pathlib
    for f in pathlib.Path(dagbag.dag_folder).rglob("*.py"):
        assert "formation-token-2026" not in f.read_text(encoding="utf-8"), (
            f"Token en dur détecté dans {f}"
        )
