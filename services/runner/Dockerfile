FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends docker.io && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir 'fastapi>=0.115,<1' 'uvicorn>=0.30,<1'
WORKDIR /worker
COPY main.py .
CMD ["uvicorn","main:app","--host","0.0.0.0","--port","8080"]
