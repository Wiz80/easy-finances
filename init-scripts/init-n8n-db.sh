#!/bin/bash
set -e

# Create n8n database if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER $POSTGRES_NON_ROOT_USER WITH PASSWORD '$POSTGRES_NON_ROOT_PASSWORD';
    CREATE DATABASE n8n OWNER $POSTGRES_NON_ROOT_USER;
    GRANT ALL PRIVILEGES ON DATABASE n8n TO $POSTGRES_NON_ROOT_USER;
EOSQL

echo "n8n database and user created successfully"


