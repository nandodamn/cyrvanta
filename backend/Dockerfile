FROM python:3.12.10-slim@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system cyrvanta && adduser --system --ingroup cyrvanta cyrvanta
COPY backend/pyproject.toml backend/alembic.ini backend/requirements.lock ./
COPY backend/alembic ./alembic
COPY backend/src ./src
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --no-deps .
# Trust the lab Wazuh manager's own-issued cert (infrastructure/wazuh/manager/certs/,
# see its README) for strict TLS verification in host.isolate/host.restore and
# Wazuh finding ingestion -- httpx uses certifi's bundle, not the OS trust store.
COPY infrastructure/wazuh/manager/certs/server.crt /tmp/wazuh-manager.crt
RUN cat /tmp/wazuh-manager.crt >> "$(python -c 'import certifi; print(certifi.where())')" \
    && rm /tmp/wazuh-manager.crt
USER cyrvanta
EXPOSE 8000
CMD ["uvicorn", "cyrvanta.main:app", "--host", "0.0.0.0", "--port", "8000"]
