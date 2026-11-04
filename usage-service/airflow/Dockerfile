# Pinned to Airflow 3.2.2 — the appVersion the official Helm chart 1.22.0 targets.
# (Verify the digest with: docker buildx imagetools inspect apache/airflow:3.2.2-python3.11)
FROM apache/airflow:3.2.2-python3.11@sha256:b54a222ee813387065acf3d7abe06a81572be29ddc786ca95f83e35f320d2da9

USER root

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gcc librdkafka-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

RUN for py in /usr/python/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do \
      [ -x "$py" ] && "$py" -m pip install --no-cache-dir --upgrade --root-user-action=ignore pip setuptools wheel || true; \
    done

RUN find / -path "*/ensurepip/_bundled/*.whl" -delete 2>/dev/null || true

USER airflow

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

RUN for p in ray litellm; do pip uninstall -y "$p" || true; done
