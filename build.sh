#!/bin/bash

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

