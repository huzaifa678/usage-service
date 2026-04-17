from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor
from aggregation.usage_aggregate import aggregate_usage_events

with DAG(
    dag_id="usage_aggregation",
    start_date=datetime(2024, 1, 1),
    schedule="*/1 * * * *",  
    catchup=False,
    max_active_runs=1,
) as dag:

    wait_for_ingestion = ExternalTaskSensor(
        task_id="wait_for_kafka_ingestion",
        external_dag_id="usage_kafka_ingestion",
        external_task_id="consume_kafka_batch",
        mode="poke",
        poke_interval=30,
        timeout=600,
    )

    aggregation_task = PythonOperator(
        task_id="aggregate_usage_events",
        python_callable=aggregate_usage_events,  
    )

    wait_for_ingestion >> aggregation_task
