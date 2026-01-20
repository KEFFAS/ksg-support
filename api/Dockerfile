FROM python:3.11-slim

WORKDIR /app

COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY api /app

ENV PYTHONUNBUFFERED=1

CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]
