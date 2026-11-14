FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock
COPY agent/pyproject.toml agent/README.md /tmp/agent/
COPY agent/src /tmp/agent/src
RUN pip install --no-cache-dir --no-deps /tmp/agent && rm -rf /tmp/agent
RUN useradd --uid 10001 --create-home forma && mkdir -p /app/data && chown forma:forma /app/data
COPY --chown=forma:forma backend/app ./app
USER forma
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
