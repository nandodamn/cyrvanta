FROM python:3.12.10-slim@sha256:fd95fa221297a88e1cf49c55ec1828edd7c5a428187e67b5d1805692d11588db AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system cyrvanta && adduser --system --ingroup cyrvanta cyrvanta
COPY pyproject.toml alembic.ini requirements.lock ./
COPY alembic ./alembic
COPY src ./src
RUN pip install --no-cache-dir --require-hashes -r requirements.lock \
    && pip install --no-cache-dir --no-deps .
USER cyrvanta
EXPOSE 8000
CMD ["uvicorn", "cyrvanta.main:app", "--host", "0.0.0.0", "--port", "8000"]
