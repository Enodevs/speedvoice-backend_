#!/bin/bash

# Collect static files
echo "Collecting static files..."
python3.12 manage.py collectstatic --noinput

