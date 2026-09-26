# NCEA Review Navigator — API container
FROM python:3.13-slim

# AWS Lambda Web Adapter: lets this same image run on AWS Lambda.
# It does nothing under docker compose. Tag 1.1.0, pinned by digest.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1 /lambda-adapter /opt/extensions/lambda-adapter

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AWS_LWA_PORT=5000 \
    AWS_LWA_READINESS_CHECK_PATH=/api/health \
    AWS_LWA_READINESS_CHECK_HEALTHY_STATUS=200-299

WORKDIR /app

# Install deps first for better layer caching.
# gunicorn (serves the app) and boto3 (S3 database mode, s3db.py) are only needed
# inside the image, so they are installed here rather than added to
# requirements.txt (which matches the submitted code).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "gunicorn>=23,<24" "boto3>=1.36,<2"

COPY . .

# Run as a non-root user; /app/data holds the SQLite file (mounted as a volume).
RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser /app
USER appuser

EXPOSE 5000

# Create the DB (idempotent) then serve with gunicorn.
CMD ["sh", "-c", "python -c 'import db; db.init_db()' && gunicorn --bind 0.0.0.0:5000 'app:app'"]
