#!/bin/bash
set -e

# Create testing database for pytest
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE finanzas_test OWNER $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE finanzas_test TO $POSTGRES_USER;
EOSQL

echo "finanzas_test database created successfully"
