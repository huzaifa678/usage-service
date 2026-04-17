from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator
from consumer.event_consume import consume_kafka_batch


with DAG(
    dag_id="usage_kafka_ingestion",
    start_date=datetime(2024, 1, 1),
    schedule="*/1 * * * *",  
    catchup=False,
    max_active_runs=1,
) as dag:

    ingest_task = PythonOperator(
        task_id="consume_kafka_batch",
        python_callable=consume_kafka_batch,
    )