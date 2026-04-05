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

# Créer les liens symboliques que Django cherche
RUN ln -sf /usr/lib/x86_64-linux-gnu/libgdal.so.36 /usr/lib/libgdal.so && \
    ln -sf /usr/lib/x86_64-linux-gnu/libgeos_c.so.1 /usr/lib/libgeos_c.so

ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal
ENV GDAL_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgdal.so.36
ENV GEOS_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/libgeos_c.so.1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir GDAL==$(gdal-config --version)

COPY . .

RUN DJANGO_SECRET_KEY=build-only \
    DB_HOST=localhost DB_NAME=postgres \
    DB_USER=postgres DB_PASSWORD=postgres DB_PORT=5432 \
    python manage.py collectstatic --no-input

EXPOSE 8000

CMD gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120