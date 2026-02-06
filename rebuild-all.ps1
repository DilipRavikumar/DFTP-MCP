# Complete Rebuild: All Docker Images from Scratch
# This will rebuild all 4 containers with fresh code

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "COMPLETE REBUILD - ALL CONTAINERS" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Clean up old images
Write-Host "Step 1: Cleaning up old Docker images..." -ForegroundColor Yellow
docker rmi backend:latest -f 2>$null
docker rmi frontend:latest -f 2>$null
docker rmi auth-gateway:latest -f 2>$null
docker rmi auth-service:latest -f 2>$null
docker rmi 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/backend:latest -f 2>$null
docker rmi 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/frontend:latest -f 2>$null
docker rmi 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-gateway:latest -f 2>$null
docker rmi 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-service:latest -f 2>$null

Write-Host "Old images removed" -ForegroundColor Green
Write-Host ""

# Step 2: Authenticate with ECR
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 2: Authenticate with ECR" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker logout 254800774891.dkr.ecr.us-east-2.amazonaws.com
aws ecr get-login-password --region us-east-2 --profile devx | docker login --username AWS --password-stdin 254800774891.dkr.ecr.us-east-2.amazonaws.com

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: ECR authentication failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Authentication successful!" -ForegroundColor Green
Write-Host ""

# BACKEND
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 3: Build Backend (Fresh)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Dockerfile.backend -t backend:latest . --no-cache

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend build failed!" -ForegroundColor Red
    exit 1
}

docker tag backend:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/backend:latest
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/backend:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Backend: BUILD + PUSH SUCCESS!" -ForegroundColor Green
Write-Host ""

# FRONTEND
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 4: Build Frontend (Fresh)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Frontend/Dockerfile -t frontend:latest ./Frontend --no-cache

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend build failed!" -ForegroundColor Red
    exit 1
}

docker tag frontend:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/frontend:latest
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/frontend:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Frontend: BUILD + PUSH SUCCESS!" -ForegroundColor Green
Write-Host ""

# AUTH GATEWAY
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 5: Build Auth Gateway (Fresh)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Auth_gateway/Dockerfile.k8s -t auth-gateway:latest ./Auth_gateway --no-cache

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Gateway build failed!" -ForegroundColor Red
    exit 1
}

docker tag auth-gateway:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-gateway:latest
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-gateway:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Gateway push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Auth Gateway: BUILD + PUSH SUCCESS!" -ForegroundColor Green
Write-Host ""

# AUTH SERVICE
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 6: Build Auth Service (Fresh)" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Auth_gateway/Dockerfile.auth -t auth-service:latest ./Auth_gateway --no-cache

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Service build failed!" -ForegroundColor Red
    exit 1
}

docker tag auth-service:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-service:latest
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-service:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Service push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Auth Service: BUILD + PUSH SUCCESS!" -ForegroundColor Green
Write-Host ""

# VERIFY
Write-Host "=====================================" -ForegroundColor Green
Write-Host "ALL 4 IMAGES REBUILT AND PUSHED!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""

Write-Host "Verifying images in ECR..." -ForegroundColor Yellow
Write-Host ""

Write-Host "Backend:" -ForegroundColor Cyan
aws ecr describe-images --repository-name dftp-mcp/backend --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host "Frontend:" -ForegroundColor Cyan
aws ecr describe-images --repository-name dftp-mcp/frontend --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host "Auth Gateway:" -ForegroundColor Cyan
aws ecr describe-images --repository-name dftp-mcp/auth-gateway --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host "Auth Service:" -ForegroundColor Cyan
aws ecr describe-images --repository-name dftp-mcp/auth-service --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "NEXT STEP: Restart Kubernetes Pods" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Run this command:" -ForegroundColor Cyan
Write-Host 'kubectl delete pod --all -n dftp-mcp' -ForegroundColor Yellow
Write-Host ""
Write-Host "Then watch them come back up:" -ForegroundColor Cyan
Write-Host 'kubectl get pods -n dftp-mcp -w' -ForegroundColor Yellow
