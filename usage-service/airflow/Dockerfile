FROM apache/airflow:3.3.2-python3.11@sha256:a6685a7a708ed6fa910c2c05458d7f2b0db9cca5c3bf58a72ded389767ad3e65

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
