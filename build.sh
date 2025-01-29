#!/usr/bin/env bash
# exit on error
set -o errexit

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    python3-pip python3-dev \
    postgresql postgresql-contrib \
    libpq-dev gcc \
    tesseract-ocr \
    libgl1-mesa-glx

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Installing gunicorn..."
pip install gunicorn

# Create necessary directories
mkdir -p static staticfiles media

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Running migrations..."
python manage.py migrate --no-input

echo "Creating superuser if none exists..."
python manage.py create_superuser_if_none_exists

# Print environment information
echo "Environment Information:"
echo "PORT: $PORT"
echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
echo "Current Directory: $(pwd)"
echo "Python Version: $(python --version)"
echo "Pip Version: $(pip --version)"

# Print installed packages
echo "Installed packages:"
pip list
