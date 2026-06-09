FROM python:3.12-slim

WORKDIR /app

COPY bishop_shared ./bishop_shared
COPY services/ui/stub_main.py ./stub_main.py

ENV PYTHONPATH=/app

CMD ["python", "stub_main.py"]
