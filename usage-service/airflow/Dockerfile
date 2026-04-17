FROM apache/airflow:3.1.7-python3.11

USER root

# Install build dependencies
RUN apt-get update && \
    apt-get install -y gcc librdkafka-dev && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

USER airflow

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Upgrade pip and install dependencies with preferred binary to avoid long builds
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt
