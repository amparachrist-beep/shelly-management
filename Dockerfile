FROM python:3.10-slim

# Variables d'environnement
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Librairies système GeoDjango + outils de compilation C++
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

# Dire à pip où trouver GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Répertoire de travail
WORKDIR /app

# Installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copier le projet
COPY . .

# Collecter les fichiers statiques
RUN python manage.py collectstatic --no-input

# Exposer le port
EXPOSE 8000

# Lancer Gunicorn
CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120