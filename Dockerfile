FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Librairies système GeoDjango
RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    gcc \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libgeos-c1v5 \
    python3-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

# 1. Installer tous les packages Django (sans GDAL)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 2. Installer GDAL avec la version exacte du système
RUN pip install --no-cache-dir GDAL==$(gdal-config --version)

# 3. Copier le projet
COPY . .

# 4. Collecter les fichiers statiques
RUN python manage.py collectstatic --no-input

EXPOSE 8000

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120