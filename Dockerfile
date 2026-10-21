FROM python:3.12-slim
# GNU Make is part of the test environment so Make integration tests run in
# `make test`'s Docker fallback instead of being silently skipped.
RUN apt-get update && apt-get install -y --no-install-recommends adb make && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bmw_export_journeys.py .
ARG PROJECT_HASH=unknown
LABEL org.bmwjourney.source="${PROJECT_HASH}"
ENTRYPOINT ["python", "/app/bmw_export_journeys.py"]
