from datetime import datetime

from usage_etl_common import EMBED_PARALLELISM, make_pod_task

from airflow.providers.standard.sensors.external_task import ExternalTaskSensor
from airflow.sdk import DAG

with DAG(
    dag_id="usage_rag_embedding",
    start_date=datetime(2024, 1, 1),
    schedule="*/1 * * * *",
    catchup=False,
    max_active_runs=1,
) as dag:
    # deferrable hands the wait to the triggerer process (deployed by the chart)
    # instead of holding a KubernetesExecutor pod slot for the whole poke window.
    wait_for_aggregation = ExternalTaskSensor(
        task_id="wait_for_usage_aggregation",
        external_dag_id="usage_aggregation",
        external_task_id="aggregate_usage_events",
        deferrable=True,
        poke_interval=30,
        timeout=600,
    )

    # Runs the `embed` image (etl.embed.process_embeddings) as its own pod;
    # EMBED_PARALLELISM > 1 fans out that many pods, kept disjoint by SKIP LOCKED.
    embedding_task = make_pod_task(
        task_id="process_usage_event_embeddings",
        component="embed",
        parallelism=EMBED_PARALLELISM,
    )

    wait_for_aggregation >> embedding_task
