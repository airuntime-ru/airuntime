FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini ./alembic.ini
COPY backend/entrypoint.sh ./entrypoint.sh
COPY backend/src ./src
COPY agents ./agents
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["sh", "/app/entrypoint.sh", "api"]
