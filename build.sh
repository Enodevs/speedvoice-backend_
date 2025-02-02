#!/bin/bash

# # Create a virtual environment
# python3.13.1 -m venv venv
# source venv/bin/activate

# Install dependencies
echo "Building the project and installing dependencies..."
pip install -r requirements.txt

# Run migrations
echo "Make Migration..."
python3.13.1 manage.py makemigrations --noinput
python3.13.1 manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput