FROM python:3.12-slim

WORKDIR /app

COPY services/vector-writer/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY bishop_shared ./bishop_shared
COPY services/vector-writer/app ./app

ENV PYTHONPATH=/app

# sentence-transformers downloads all-MiniLM-L6-v2 on first encoder init.
CMD ["python", "-m", "app.main"]
