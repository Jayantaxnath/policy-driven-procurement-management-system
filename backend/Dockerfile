FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY Cantill_FullStack_Task_Kit /app/Cantill_FullStack_Task_Kit
COPY procurement.db /app/procurement.db

WORKDIR /app/backend

EXPOSE 8000

CMD ["sh", "-c", "PYTHONPATH=/app/backend python app/db/seed.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
