# Pinned to Airflow 3.3.2 (patched) — fixes CVE-2026-33264 (CRITICAL: RCE via unsafe
# serialized DAG deserialization) and CVE-2026-68968 (Backfill API cross-DAG authz bypass).
# The official Helm chart 1.22.0 still DEFAULTS to appVersion 3.2.2, but the chart's
# values.yaml (saas-continious-delivery/gitops/infra/airflow) overrides images.airflow to
# this custom image, so the chart's Airflow-3.x templates run this patched 3.3.2 binary.
# Move the chart to its own 3.3.x line once one is published.
# (Verify the digest with: docker buildx imagetools inspect apache/airflow:3.3.2-python3.11)
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

# Reproducible installs via the pinned uv build tool (matches Dockerfile.api/.consumer/
# .aggregation/.embed). Unlike those slim job images, this one layers on the apache/airflow
# base, so uv installs into airflow's existing environment with `uv pip install` rather than
# `uv sync` from uv.lock — that lock describes the ETL/API job images' deps, not the
# orchestrator's. uv is an ephemeral build tool, removed at the end.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

USER airflow

COPY requirements.txt .

RUN uv pip install --python "$(command -v python)" --no-cache -r requirements.txt

# Upgrade the airflow env's own pip. pip VENDORS certifi/msgpack/urllib3 under pip/_vendor,
# and Trivy reads their versions from pip/_vendor/vendor.txt.
RUN uv pip install --python "$(command -v python)" --no-cache --upgrade "pip>=26.3"

# Remove packages the orchestrator never imports. ray/litellm are heavy ETL-only deps; the
# `uv` PyPI package (0.12.10) is a leaf (nothing Required-by it) that the base image ships
# and that bundles the compromised emSign root CA (GHSA-hq85-5cpj-mr62, CRITICAL) — the
# build uses the standalone /bin/uv binary, not this wheel, so dropping it clears the
# finding at the source. (The uv/uvx/prek tool binaries are removed below.)
RUN for p in ray litellm uv; do uv pip uninstall --python "$(command -v python)" "$p" || true; done

# Drop the base image's bundled uv/uvx/prek dev tooling. It isn't used at runtime by any
# orchestrator process.
RUN rm -rf \
      /home/airflow/.local/bin/uv \
      /home/airflow/.local/bin/uvx \
      /home/airflow/.local/bin/prek \
      /home/airflow/.local/share/uv

USER root
RUN rm -f /bin/uv
USER airflow
