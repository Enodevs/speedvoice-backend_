#!/bin/bash

# Collect static files
echo "Collecting static files..."
python3.13.1 manage.py collectstatic --noinput

