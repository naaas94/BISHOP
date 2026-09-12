FROM python:3.12-slim

WORKDIR /app

COPY services/enrichment-batcher/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bishop_shared ./bishop_shared
COPY config/profiles ./config/profiles
COPY config/prompts ./config/prompts
COPY services/enrichment-batcher/app ./app

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
