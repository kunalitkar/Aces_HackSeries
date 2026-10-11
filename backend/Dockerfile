# Backend image. Works with EITHER build context:
#   * repository root     (render.yaml / "Root Directory" empty, Dockerfile Path ./backend/Dockerfile)
#   * the backend/ folder (Render "Root Directory" = backend, Dockerfile Path ./Dockerfile)
# Local build from the repo root:  docker build -f backend/Dockerfile -t agrisentry-api .
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv

# Copy the build context, then keep only what the backend needs, laid out as /srv/backend/{app,scripts,requirements.txt}.
COPY . /tmp/ctx
RUN set -e; \
    if [ -d /tmp/ctx/backend/app ]; then SRC=/tmp/ctx/backend; else SRC=/tmp/ctx; fi; \
    test -d "$SRC/app" && test -f "$SRC/requirements.txt" || { echo "ERROR: could not find app/ and requirements.txt in the build context"; ls -la /tmp/ctx; exit 1; }; \
    mkdir -p /srv/backend/scripts; \
    cp -r "$SRC/app" "$SRC/requirements.txt" /srv/backend/; \
    cp "$SRC/scripts/download_model.py" /srv/backend/scripts/; \
    rm -rf /tmp/ctx

RUN pip install --no-cache-dir -r backend/requirements.txt

# ONNX weights and classes.json come from Hugging Face at build time, SHA-256 verified (the build fails on a mismatch).
RUN python backend/scripts/download_model.py

WORKDIR /srv/backend
EXPOSE 8000
# Hosts such as Render/Railway inject $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
