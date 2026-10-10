from datetime import datetime

from usage_etl_common import make_pod_task

from airflow import DAG

with DAG(
    dag_id="usage_kafka_ingestion",
    start_date=datetime(2024, 1, 1),
    schedule="*/1 * * * *",
    catchup=False,
    max_active_runs=1,
) as dag:
    # Runs the `consumer` image (etl.ingest.consume_kafka_batch) as its own pod.
    make_pod_task(task_id="consume_kafka_batch", component="consumer")
