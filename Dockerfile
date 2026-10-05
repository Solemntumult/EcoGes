FROM python:3.12-slim

# Empêcher Python d'écrire des fichiers .pyc et forcer l'affichage immédiat des logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances système requises :
# - libpq-dev, build-essential : pour PostgreSQL et extensions C
# - libpango, libcairo, libgdk-pixbuf, fonts : requis par WeasyPrint pour générer les PDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libpq-dev \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . /app/

# Port exposé pour l'application Django
EXPOSE 8000

# Commande par défaut pour lancer le serveur de développement Django
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
