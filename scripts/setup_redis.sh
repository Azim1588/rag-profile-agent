#!/bin/bash
# Setup Redis
# This script requires sudo access

set -e

echo "Starting Redis service..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

echo "Testing Redis connection..."
redis-cli ping

echo "✓ Redis setup complete!"

# Optional: Configure Redis for production
# Uncomment the following lines if you want to set memory limits:
# echo "Configuring Redis..."
# sudo sed -i 's/# maxmemory <bytes>/maxmemory 256mb/' /etc/redis/redis.conf
# sudo sed -i 's/# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
# sudo systemctl restart redis-server

