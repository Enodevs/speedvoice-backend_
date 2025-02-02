#!/bin/bash

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();

User.objects.create_superuser('admin', 'admin@example.com', 'adminpassword');
if not User.objects.filter(username='admin').exists() else print('Superuser already exists');
"

# Collect static files
python manage.py collectstatic --noinput