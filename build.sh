#!/bin/bash

# Set errexit option: Exit immediately if a command exits with a non-zero status.
set -o errexit  

# Install project dependencies from requirements.txt
echo "Installing requirements..."
pip install -r requirements.txt

# Collect static files (CSS, JavaScript, images) into the STATIC_ROOT directory. --noinput prevents prompting for confirmation.
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Apply database migrations to the project's database.
echo "Migrating the project"
python manage.py migrate

