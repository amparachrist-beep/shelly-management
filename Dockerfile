FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Librairies système + python3-gdal précompilé
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    libgeos-dev \
    libgeos-c1v5 \
    python3-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Variables pour que pip trouve les headers GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

WORKDIR /app

COPY requirements.txt .

# Installer tous les packages SAUF GDAL, puis GDAL avec version exacte du système
RUN pip install --no-cache-dir --upgrade pip && \
    grep -v "^GDAL" requirements.txt > requirements_no_gdal.txt && \
    pip install --no-cache-dir -r requirements_no_gdal.txt && \
    pip install --no-cache-dir GDAL==$(gdal-config --version)

COPY . .

RUN python manage.py collectstatic --no-input

EXPOSE 8000

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120