# Backend image. Build from the repository root:  docker build -f backend/Dockerfile -t agrisentry-api .
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app backend/app
COPY backend/scripts/download_model.py backend/scripts/download_model.py
COPY models/classes.json models/classes.json
# Fetch the ONNX weights from Hugging Face at build time and verify SHA-256 (fails the build on mismatch).
RUN python backend/scripts/download_model.py
WORKDIR /app/backend
EXPOSE 8000
# Hosts such as Render/Railway inject $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
