FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Installer Python pip et dépendances système
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    postgresql-client \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier requirements sans la ligne GDAL (déjà installé dans l'image)
COPY requirements.txt .
RUN sed 's/\r//' requirements.txt | grep -v "^GDAL" > requirements_clean.txt && \
    pip install --no-cache-dir --break-system-packages -r requirements_clean.txt

COPY . .

RUN python3 manage.py collectstatic --no-input

EXPOSE 8000

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120