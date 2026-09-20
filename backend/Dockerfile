FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The MAX Bot API (platform-api2.max.ru) is signed by the Ministry of Digital Development's
# "Russian Trusted Sub CA", which ships in no default trust store. Without this the bot fails
# every call with CERTIFICATE_VERIFY_FAILED and silently never delivers a message.
# Provenance and fingerprints: infra/certs/README.md
COPY infra/certs/russian-trusted-ca.crt /usr/local/share/ca-certificates/russian-trusted-ca.crt
RUN update-ca-certificates

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini ./alembic.ini
COPY backend/entrypoint.sh ./entrypoint.sh
COPY backend/src ./src
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["sh", "/app/entrypoint.sh", "api"]
