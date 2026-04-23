FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by pytr (cryptography, curl_cffi)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default: run pipeline for the current week
ENTRYPOINT ["python", "main.py"]
CMD ["run"]
