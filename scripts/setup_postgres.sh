#!/bin/bash
# Setup PostgreSQL with pgvector
# This script requires sudo access

set -e

echo "Starting PostgreSQL service..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

echo "Creating database and user..."
sudo -u postgres psql << EOF
CREATE DATABASE profile_agent;
CREATE USER profile_user WITH PASSWORD 'secure_password_123';
GRANT ALL PRIVILEGES ON DATABASE profile_agent TO profile_user;
\q
EOF

echo "Enabling pgvector extension..."
sudo -u postgres psql -d profile_agent << EOF
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
\q
EOF

echo "Running database schema..."
sudo -u postgres psql -d profile_agent -f scripts/init_db.sql

echo "Verifying tables were created..."
sudo -u postgres psql -d profile_agent -c "\dt"

echo "✓ PostgreSQL setup complete!"

