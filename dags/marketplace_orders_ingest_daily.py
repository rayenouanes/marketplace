from datetime import datetime

from airflow.sdk import dag, task


@dag(
    dag_id="marketplace_orders_ingest_daily",
    schedule="@daily",
    start_date=datetime(2026, 4, 1),
    catchup=False,
    tags=["marketplace", "elt"],
)
def marketplace_pipeline():

    @task
    def demarrage():
        print("Démarrage du pipeline Marketplace")
        print("Infrastructure Airflow opérationnelle")

    @task
    def fin():
        print("Fin du test d'orchestration")

    demarrage() >> fin()


marketplace_pipeline()
