#!/bin/bash

echo "=========================================="
echo "Clinical Decision Support System Setup"
echo "=========================================="

# Create Python virtual environment
echo "Creating virtual environment..."
python -m venv .venv
source .venv/Scripts/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment template
echo "Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please configure with your API keys."
fi

# Start Docker services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services
echo "Waiting for services to be healthy..."
sleep 10

# Initialize Django database
echo "Initializing Django database..."
cd web/django_app
python manage.py migrate
cd ../..

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  - FastAPI:    http://localhost:8001"
echo "  - Django:     http://localhost:8002"
echo "  - Neo4j:      http://localhost:7474"
echo "  - ChromaDB:   http://localhost:8000"
echo ""
echo "Next steps:"
echo "  1. Update .env with your API keys"
echo "  2. Start the API server: uvicorn api.main:app --reload"
echo "  3. Start Django: cd web/django_app && python manage.py runserver"
echo ""
