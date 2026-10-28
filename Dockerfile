FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc libpq-dev protobuf-compiler curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SERVICE_PORT=8001
ENV SERVICE_MODULE=services.user_service.main

EXPOSE 8001

CMD sh -c "python -m uvicorn ${SERVICE_MODULE}:app --host 0.0.0.0 --port ${SERVICE_PORT}"
