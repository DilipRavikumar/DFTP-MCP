# Can_ser Docker Deployment

This directory contains Docker configuration for running the Can_ser service with all its dependencies.

## 🏗️ Architecture

The Docker setup includes:

- **Can_ser Application** (Port 8086)
- **PostgreSQL Database** (Port 5432)
- **Redis** (Port 6379) - for status streaming
- **ActiveMQ** (Ports 61616, 8161) - for message queuing

## 📋 Prerequisites

- Docker Desktop installed and running
- Docker Compose V2
- At least 4GB RAM available for containers
- Ports 5432, 6379, 8086, 8161, 61616 available

## 🚀 Quick Start

### Option 1: Using PowerShell Script (Windows)
```powershell
.\deploy.ps1
```

### Option 2: Using Bash Script (Linux/Mac/WSL)
```bash
chmod +x deploy.sh
./deploy.sh
```

### Option 3: Manual Docker Compose
```bash
# Create required directories
mkdir -p temp logs

# Start all services
docker-compose up --build -d

# View logs
docker-compose logs -f can-ser
```

## 🔧 Configuration

### Environment Variables
The application uses these key environment variables in Docker:

- `SPRING_DATASOURCE_URL`: PostgreSQL connection string
- `SPRING_DATA_REDIS_HOST`: Redis hostname
- `SPRING_ACTIVEMQ_BROKER_URL`: ActiveMQ broker URL
- `AWS_SQS_ENABLED`: Enable/disable SQS integration
- `JAVA_OPTS`: JVM configuration

### Database Migration
The PostgreSQL container automatically:
1. Creates the `canonical_db` database
2. Runs initialization scripts from `init-scripts/`
3. Hibernate creates tables on first application start

## 📊 Service Endpoints

| Service | URL | Purpose |
|---------|-----|---------|
| Can_ser App | http://localhost:8086 | Main application |
| Health Check | http://localhost:8086/actuator/health | Application health |
| PostgreSQL | localhost:5432 | Database connection |
| Redis | localhost:6379 | Cache/streaming |
| ActiveMQ Console | http://localhost:8161 | Message queue management |

### Default Credentials
- **PostgreSQL**: postgres/root@123
- **ActiveMQ**: admin/admin
- **Redis**: No authentication

## 🔍 Monitoring & Troubleshooting

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f can-ser
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f activemq
```

### Check Service Status
```bash
# All services
docker-compose ps

# Service health
curl http://localhost:8086/actuator/health
```

### Connect to Database
```bash
# Using docker
docker-compose exec postgres psql -U postgres -d canonical_db

# Using external client
psql -h localhost -p 5432 -U postgres -d canonical_db
```

### Check Redis
```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli

# Check Redis status
docker-compose exec redis redis-cli ping
```

## 🛑 Management Commands

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Clean Restart (removes volumes)
```bash
docker-compose down -v
docker-compose up --build -d
```

### Update Application Only
```bash
docker-compose build can-ser
docker-compose up -d can-ser
```

## 📁 Directory Structure

```
Can_ser/
├── docker-compose.yml      # Main orchestration file
├── Dockerfile             # Can_ser application image
├── deploy.ps1            # Windows deployment script
├── deploy.sh             # Linux/Mac deployment script
├── redis.conf            # Redis configuration
├── .dockerignore         # Docker build ignore file
├── init-scripts/         # Database initialization
│   └── 01-init-database.sql
├── temp/                 # File processing temp directory
├── logs/                 # Application logs
└── src/                  # Application source code
    └── main/
        └── resources/
            ├── application.yml         # Default config
            └── application-docker.yml  # Docker-specific config
```

## 🔧 Customization

### Modify Database Settings
Edit `docker-compose.yml` under the `postgres` service or set environment variables.

### Change Application Configuration
1. Edit `src/main/resources/application-docker.yml`
2. Rebuild: `docker-compose build can-ser`
3. Restart: `docker-compose up -d can-ser`

### Add Custom Database Scripts
Place `.sql` files in the `init-scripts/` directory. They run in alphabetical order.

### Performance Tuning
Adjust JVM settings in `docker-compose.yml` under `can-ser` service `JAVA_OPTS`.

## 🔒 Security Notes

- Default passwords are used for development
- Change passwords for production deployment
- Network is isolated using Docker bridge network
- Application runs as non-root user in container

## 📞 Support

For issues:
1. Check service logs: `docker-compose logs -f [service-name]`
2. Verify all containers are running: `docker-compose ps`
3. Check resource usage: `docker stats`
4. Restart problematic service: `docker-compose restart [service-name]`