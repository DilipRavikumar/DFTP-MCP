# Build and Push Docker Images to ECR
# Run this script from: C:\Users\dilip\Documents\MCP\DFTP-MCP

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 1: Authenticate with ECR" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

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
Write-Host "Step 2: Build Backend Image" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Dockerfile.backend -t backend:latest .

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Tagging backend image..." -ForegroundColor Yellow
docker tag backend:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/backend:latest

Write-Host "Pushing backend image to ECR..." -ForegroundColor Yellow
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/backend:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Backend push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Backend image pushed successfully!" -ForegroundColor Green

# FRONTEND
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 3: Build Frontend Image" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Frontend/Dockerfile -t frontend:latest ./Frontend

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Tagging frontend image..." -ForegroundColor Yellow
docker tag frontend:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/frontend:latest

Write-Host "Pushing frontend image to ECR..." -ForegroundColor Yellow
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/frontend:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Frontend push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Frontend image pushed successfully!" -ForegroundColor Green

# AUTH GATEWAY
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 4: Build Auth Gateway Image" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Auth_gateway/Dockerfile.k8s -t auth-gateway:latest ./Auth_gateway

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Gateway build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Tagging auth-gateway image..." -ForegroundColor Yellow
docker tag auth-gateway:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-gateway:latest

Write-Host "Pushing auth-gateway image to ECR..." -ForegroundColor Yellow
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-gateway:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Gateway push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Auth Gateway image pushed successfully!" -ForegroundColor Green

# AUTH SERVICE
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 5: Build Auth Service Image" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

docker build -f Auth_gateway/Dockerfile.auth -t auth-service:latest ./Auth_gateway

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Service build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Tagging auth-service image..." -ForegroundColor Yellow
docker tag auth-service:latest 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-service:latest

Write-Host "Pushing auth-service image to ECR..." -ForegroundColor Yellow
docker push 254800774891.dkr.ecr.us-east-2.amazonaws.com/dftp-mcp/auth-service:latest

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Auth Service push failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Auth Service image pushed successfully!" -ForegroundColor Green

# VERIFY
Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Step 6: Verify Images in ECR" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "Checking backend..." -ForegroundColor Yellow
aws ecr describe-images --repository-name dftp-mcp/backend --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host "Checking frontend..." -ForegroundColor Yellow
aws ecr describe-images --repository-name dftp-mcp/frontend --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host "Checking auth-gateway..." -ForegroundColor Yellow
aws ecr describe-images --repository-name dftp-mcp/auth-gateway --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host "Checking auth-service..." -ForegroundColor Yellow
aws ecr describe-images --repository-name dftp-mcp/auth-service --region us-east-2 --profile devx --query 'imageDetails[0].imageTags' --output text

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "ALL IMAGES PUSHED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green

Write-Host ""
Write-Host "Next step: Restart the pods to pull new images" -ForegroundColor Cyan
Write-Host "Run: kubectl delete pod --all -n dftp-mcp" -ForegroundColor Yellow
