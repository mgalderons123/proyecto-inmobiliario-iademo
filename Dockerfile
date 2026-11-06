FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-qa.txt ./
RUN python -m pip install --no-cache-dir -r requirements-qa.txt

RUN useradd --create-home --uid 1000 casarent \
    && mkdir -p /app/staticfiles /app/data/public /app/data/private \
    && chown -R casarent:casarent /app

COPY --chown=casarent:casarent . .

RUN chmod +x /app/scripts/qa-entrypoint.sh

USER casarent

EXPOSE 8000

ENTRYPOINT ["/app/scripts/qa-entrypoint.sh"]
