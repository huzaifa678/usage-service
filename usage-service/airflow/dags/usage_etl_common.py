import os

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

# Injected via the Airflow chart's extraEnv (per-env values-<env>.yaml).
IMAGE_REPO = os.environ.get("USAGE_ETL_IMAGE_REPO", "usage-service")
IMAGE_TAG = os.environ.get("USAGE_ETL_IMAGE_TAG", "dev")
NAMESPACE = os.environ.get("USAGE_ETL_NAMESPACE", "airflow")
ENV_SECRET = os.environ.get("USAGE_ETL_ENV_SECRET", "usage-etl-env")
# Optional: a ServiceAccount for the task pods (e.g. MSK SASL/IAM Pod Identity for the
# Kafka consumer). Empty -> the namespace default SA.
SERVICE_ACCOUNT = os.environ.get("USAGE_ETL_SERVICE_ACCOUNT") or None


def make_pod_task(task_id: str, component: str) -> KubernetesPodOperator:
    """Build a KubernetesPodOperator that runs one ETL stage image.

    component is one of: "consumer" (ingest), "aggregation", "embed".
    """
    return KubernetesPodOperator(
        task_id=task_id,
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
