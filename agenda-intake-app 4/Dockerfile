FROM python:3.11-slim

# LibreOffice (headless) is used to convert Word documents to PDF.
RUN apt-get update && \
    apt-get install -y --no-install-recommends libreoffice && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

ENV PORT=8080
EXPOSE 8080

# Uses shell form so ${PORT} is read at container start, not build time.
# Railway (and similar platforms) inject their own PORT value — this falls
# back to 8080 for local `docker run` when PORT isn't set.
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 120 app:app
