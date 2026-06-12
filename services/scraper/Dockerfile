FROM python:3.12-slim

WORKDIR /app

COPY services/scraper/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bishop_shared ./bishop_shared
COPY services/scraper/app ./app
COPY services/scraper/stub_main.py ./stub_main.py

ENV PYTHONPATH=/app

CMD ["python", "stub_main.py"]
