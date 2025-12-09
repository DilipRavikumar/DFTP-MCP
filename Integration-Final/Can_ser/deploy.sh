#!/bin/bash

# Can_ser Docker Deployment Script

set -e

echo "🐳 Starting Can_ser Docker Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create necessary directories
print_status "Creating required directories..."
mkdir -p ./temp
mkdir -p ./logs

# Stop existing containers if running
print_status "Stopping existing containers..."
docker-compose down || true

# Clean up old images (optional)
if [ "$1" = "--clean" ]; then
    print_status "Cleaning up old images..."
    docker system prune -f
    docker volume prune -f
fi

# Build and start services
print_status "Building and starting services..."
docker-compose up --build -d

# Wait for services to be ready
print_status "Waiting for services to start..."
sleep 10

# Check service health
print_status "Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U postgres -d canonical_db > /dev/null 2>&1; then
    print_success "PostgreSQL is ready"
else
    print_error "PostgreSQL is not ready"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    print_success "Redis is ready"
else
    print_error "Redis is not ready"
fi

# Check ActiveMQ
if curl -f http://localhost:8161/ > /dev/null 2>&1; then
    print_success "ActiveMQ is ready"
else
    print_warning "ActiveMQ may still be starting up"
fi

# Check Can_ser application
print_status "Waiting for Can_ser application to start..."
for i in {1..30}; do
    if curl -f http://localhost:8086/actuator/health > /dev/null 2>&1; then
        print_success "Can_ser application is ready"
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
print_success "🚀 Can_ser Docker deployment completed!"
print_status "Services:"
print_status "  📊 Can_ser Application: http://localhost:8086"
print_status "  🗄️  PostgreSQL: localhost:5432"
print_status "  🔴 Redis: localhost:6379"
print_status "  📨 ActiveMQ Console: http://localhost:8161"
print_status ""
print_status "📋 To view logs:"
print_status "  docker-compose logs -f can-ser"
print_status ""
print_status "🛑 To stop services:"
print_status "  docker-compose down"