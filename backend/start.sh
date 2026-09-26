#!/bin/sh

# Wait for MySQL
echo "Waiting for MySQL..."
while ! nc -z localhost 3306; do
  sleep 0.1
done
echo "MySQL started"

# Try to run migrations. If it fails (e.g. no versions), generate the initial one.
alembic upgrade head || {
    echo "No migrations found or upgrade failed. Generating initial migration..."
    alembic revision --autogenerate -m "Initial migration"
    alembic upgrade head
}

echo "Starting backend..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
