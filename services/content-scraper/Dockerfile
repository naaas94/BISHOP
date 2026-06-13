FROM python:3.12-slim

WORKDIR /app

COPY services/content-scraper/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bishop_shared ./bishop_shared
COPY services/content-scraper/app ./app

# Vendor scraper adapter layer as scraper_app (M4 Flag 2 — avoids ``app`` collision).
COPY services/scraper/app ./scraper_app
RUN find ./scraper_app -name '*.py' -exec sed -i \
    -e 's/from app\./from scraper_app./g' \
    -e 's/import app\./import scraper_app./g' {} +

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
