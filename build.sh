#!/usr/bin/env bash
# exit on error
set -o errexit

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

echo "Upgrading pip..."
python -m pip install --upgrade pip

echo "Installing Python dependencies..."
pip install --no-cache-dir -r requirements.txt

# Install specific packages needed for OpenCV and image processing
pip install --no-cache-dir \
    opencv-python-headless \
    numpy \
    pillow \
    scikit-learn \
    gunicorn \
    psycopg2-binary \
    whitenoise \
    dj-database-url

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
