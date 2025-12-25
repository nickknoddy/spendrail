#!/bin/bash
# GCP Compute Engine Deployment Script for Spend-Rail API
# Assumes Docker and Docker Compose are already installed

set -e

echo "===== Spend-Rail API Deployment Script ====="
echo ""

# Check if GEMINI_API_KEY is provided
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Error: GEMINI_API_KEY environment variable is not set"
    echo "Usage: GEMINI_API_KEY=your-key ./deploy.sh"
    exit 1
fi

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

echo "[1/3] Creating environment configuration..."
cat > .env << EOF
GEMINI_API_KEY=$GEMINI_API_KEY
APP_ENV=production
DEBUG=false
LOG_FORMAT=json
LOG_LEVEL=INFO
CORS_ORIGINS=*
HOST=0.0.0.0
PORT=8000
EOF

echo "[2/3] Building Docker image..."
docker-compose build

echo "[3/3] Starting the application..."
docker-compose up -d

echo ""
echo "===== Deployment Complete ====="
echo ""
echo "Container status:"
docker ps --filter name=spend-rail-api --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""
echo "Health check:"
sleep 3
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "Waiting for service to start..."
echo ""
echo "Useful commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Stop:         docker-compose down"
echo "  Restart:      docker-compose restart"
echo ""
