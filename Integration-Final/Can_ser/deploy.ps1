# Can_ser Docker Deployment Script for Windows PowerShell

param(
    [switch]$Clean
)

Write-Host "🐳 Starting Can_ser Docker Deployment..." -ForegroundColor Blue

function Write-Status {
    param($Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param($Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param($Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param($Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

try {
    # Create necessary directories
    Write-Status "Creating required directories..."
    if (!(Test-Path ".\temp")) { New-Item -ItemType Directory -Path ".\temp" -Force }
    if (!(Test-Path ".\logs")) { New-Item -ItemType Directory -Path ".\logs" -Force }

    # Stop existing containers if running
    Write-Status "Stopping existing containers..."
    docker-compose down 2>$null

    # Clean up old images (optional)
    if ($Clean) {
        Write-Status "Cleaning up old images..."
        docker system prune -f
        docker volume prune -f
    }

    # Build and start services
    Write-Status "Building and starting services..."
    docker-compose up --build -d

    if ($LASTEXITCODE -ne 0) {
        throw "Docker compose failed to start services"
    }

    # Wait for services to be ready
    Write-Status "Waiting for services to start..."
    Start-Sleep -Seconds 10

    # Check service health
    Write-Status "Checking service health..."

    # Check PostgreSQL
    $postgresCheck = docker-compose exec -T postgres pg_isready -U postgres -d canonical_db 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "PostgreSQL is ready"
    } else {
        Write-Error "PostgreSQL is not ready"
    }

    # Check Redis
    $redisCheck = docker-compose exec -T redis redis-cli ping 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Redis is ready"
    } else {
        Write-Error "Redis is not ready"
    }

    # Check ActiveMQ
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8161/" -UseBasicParsing -TimeoutSec 5 2>$null
        Write-Success "ActiveMQ is ready"
    } catch {
        Write-Warning "ActiveMQ may still be starting up"
    }

    # Check Can_ser application
    Write-Status "Waiting for Can_ser application to start..."
    $maxAttempts = 30
    $attempt = 0
    $appReady = $false

    do {
        $attempt++
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8086/actuator/health" -UseBasicParsing -TimeoutSec 5 2>$null
            if ($response.StatusCode -eq 200) {
                Write-Success "Can_ser application is ready"
                $appReady = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 2
        }
    } while ($attempt -lt $maxAttempts)

    if (-not $appReady) {
        Write-Warning "Can_ser application may still be starting up"
    }

    Write-Host ""
    Write-Success "🚀 Can_ser Docker deployment completed!"
    Write-Status "Services:"
    Write-Status "  📊 Can_ser Application: http://localhost:8086"
    Write-Status "  🗄️  PostgreSQL: localhost:5432"
    Write-Status "  🔴 Redis: localhost:6379"
    Write-Status "  📨 ActiveMQ Console: http://localhost:8161"
    Write-Status ""
    Write-Status "📋 To view logs:"
    Write-Status "  docker-compose logs -f can-ser"
    Write-Status ""
    Write-Status "🛑 To stop services:"
    Write-Status "  docker-compose down"

} catch {
    Write-Error "Deployment failed: $_"
    exit 1
}