import os

from kubernetes.client import models as k8s

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

# Injected via the Airflow chart's extraEnv (per-env values-<env>.yaml).
IMAGE_REPO = os.environ.get("USAGE_ETL_IMAGE_REPO", "usage-service")
IMAGE_TAG = os.environ.get("USAGE_ETL_IMAGE_TAG", "dev")
NAMESPACE = os.environ.get("USAGE_ETL_NAMESPACE", "airflow")
ENV_SECRET = os.environ.get("USAGE_ETL_ENV_SECRET", "usage-etl-env")
# Optional: a ServiceAccount for the task pods (e.g. MSK SASL/IAM Pod Identity for the
# Kafka consumer). Empty -> the namespace default SA.
SERVICE_ACCOUNT = os.environ.get("USAGE_ETL_SERVICE_ACCOUNT") or None

# Horizontal fan-out per stage (default 1 = single pod, current behaviour).
# Consumer pods share group.id, so Kafka splits partitions across them: keep
# INGEST_PARALLELISM <= the topic's partition count. Embed pods stay disjoint
# via SELECT ... FOR UPDATE SKIP LOCKED. Aggregation is a single global run and
# is not fanned out.
INGEST_PARALLELISM = int(os.environ.get("USAGE_ETL_INGEST_PARALLELISM", "1"))
EMBED_PARALLELISM = int(os.environ.get("USAGE_ETL_EMBED_PARALLELISM", "1"))


def make_pod_task(
    task_id: str,
    component: str,
    parallelism: int = 1,
    extra_env: dict[str, str] | None = None,
):
    """Build a KubernetesPodOperator that runs one ETL stage image.

    component is one of: "consumer" (ingest), "aggregation", "embed".
    parallelism > 1 returns a dynamically-mapped task that launches that many
    identical pods in parallel. extra_env adds pod-level env vars on top of the
    usage-etl-env Secret (e.g. AGGREGATE_FULL_REFRESH for the true-up DAG).
    """
    base_env = [
        k8s.V1EnvVar(name=name, value=value)
        for name, value in (extra_env or {}).items()
    ]
    common = dict(
        name=f"usage-{component}",
        namespace=NAMESPACE,
        image=f"{IMAGE_REPO}:{component}-{IMAGE_TAG}",
        service_account_name=SERVICE_ACCOUNT,
        # Shared DB / Kafka / provider config lives in the usage-etl-env Secret.
        env_from=[
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name=ENV_SECRET)),
        ],
        in_cluster=True,
        get_logs=True,
        on_finish_action="delete_pod",
        reattach_on_restart=True,
        labels={"app": "usage-etl", "component": component},
    )

    if parallelism <= 1:
        return KubernetesPodOperator(
            task_id=task_id, env_vars=base_env or None, **common
        )

    # One mapped instance per shard. The pods are identical; USAGE_ETL_SHARD is
    # informational only (Kafka rebalance / SKIP LOCKED do the real splitting).
    return KubernetesPodOperator.partial(task_id=task_id, **common).expand(
        env_vars=[
            base_env + [k8s.V1EnvVar(name="USAGE_ETL_SHARD", value=str(i))]
            for i in range(parallelism)
        ]
    )
