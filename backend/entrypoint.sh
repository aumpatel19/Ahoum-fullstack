#!/bin/sh
set -e

python scripts/wait_for_db.py

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting admin static files..."
python manage.py collectstatic --noinput --clear >/dev/null

# Only on a genuinely empty database, so a restart never rewrites real data.
python manage.py seed --only-if-empty

echo "Starting gunicorn on :8000"
exec gunicorn config.wsgi:application \
    --workers 2 \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile - \
    --timeout 60
