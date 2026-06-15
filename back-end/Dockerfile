# NCEA Review Navigator — API container
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user; /app/data holds the SQLite file (mounted as a volume).
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser /app
USER appuser

EXPOSE 5000

# Create the DB (idempotent) then serve with gunicorn.
CMD ["sh", "-c", "python -c 'import db; db.init_db()' && gunicorn --bind 0.0.0.0:5000 'app:app'"]
