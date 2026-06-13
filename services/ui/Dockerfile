FROM python:3.12-slim

WORKDIR /app

COPY services/ui/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bishop_shared ./bishop_shared
COPY services/ui/app ./app
COPY services/ui/static ./static

ENV PYTHONPATH=/app

CMD ["python", "-m", "app.main"]
