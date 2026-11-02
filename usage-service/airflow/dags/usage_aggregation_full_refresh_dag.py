from datetime import datetime

from usage_etl_common import make_pod_task

from airflow import DAG

with DAG(
    dag_id="usage_aggregation_full_refresh",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
) as dag:
    # Slow-cadence true-up for the per-minute incremental `usage_aggregation`
    # DAG. Runs the `aggregation` image with AGGREGATE_FULL_REFRESH=true, which
    # recomputes every key's day/month/rolling windows regardless of the
    # `processed` flag. This re-zeroes keys that went silent (the incremental
    # run only touches keys with new events, so their daily/monthly totals would
    # otherwise never reset at a period boundary). @daily fires at midnight UTC,
    # exactly when the day/month windows roll over.
    make_pod_task(
        task_id="full_refresh_usage_aggregates",
        component="aggregation",
        extra_env={"AGGREGATE_FULL_REFRESH": "true"},
    )
