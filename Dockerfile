# Lean Standardbild: nur das [server]-Extra, SQLite als Default-DB (siehe docs/docker.md).
# Für MySQL/PostgreSQL zusätzliche Extras per Build-Arg aktivieren, z. B.:
# docker build --build-arg EXTRAS=server,postgres .
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        poppler-utils \
        libimage-exiftool-perl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY src ./src

ARG EXTRAS=server
RUN pip install --no-cache-dir ".[${EXTRAS}]"

# Default-DB liegt in einem eigenen Verzeichnis, nicht im Arbeitsverzeichnis der
# Anwendung -- als Volume mountbar, damit SQLite-Daten einen Container-Neustart
# überleben. Für Produktivbetrieb stattdessen USMEDIAKIT_DB auf MariaDB/PostgreSQL
# zeigen lassen (siehe docs/docker.md) -- dann ist dieses Volume irrelevant.
ENV USMEDIAKIT_DB=sqlite:////data/us_mediakit.db
VOLUME ["/data"]

EXPOSE 8000

COPY deploy/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["us-mediakit", "serve", "--host", "0.0.0.0", "--port", "8000"]
