from datetime import datetime

from airflow import DAG
from airflow.sensors.external_task import ExternalTaskSensor
from usage_etl_common import make_pod_task

with DAG(
    dag_id="usage_rag_embedding",
    start_date=datetime(2024, 1, 1),
    schedule="*/1 * * * *",
    catchup=False,
    max_active_runs=1,
) as dag:
    wait_for_aggregation = ExternalTaskSensor(
        task_id="wait_for_usage_aggregation",
        external_dag_id="usage_aggregation",
        external_task_id="aggregate_usage_events",
        mode="poke",
        poke_interval=30,
        timeout=600,
    )

    # Runs the `embed` image (etl.embed.process_embeddings) as its own pod.
    embedding_task = make_pod_task(
        task_id="process_usage_event_embeddings", component="embed"
    )

    wait_for_aggregation >> embedding_task
