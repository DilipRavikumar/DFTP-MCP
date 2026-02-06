# Custom Keycloak Theme Deployment Script
# Copies custom theme to Keycloak pod

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Deploying Custom Keycloak Theme" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Get Keycloak pod name
Write-Host "Step 1: Finding Keycloak pod..." -ForegroundColor Yellow
$POD_NAME = kubectl get pods -n dftp-mcp -l app=keycloak -o jsonpath='{.items[0].metadata.name}'

if (-not $POD_NAME) {
    Write-Host "ERROR: Could not find Keycloak pod!" -ForegroundColor Red
    exit 1
}

Write-Host "Found Keycloak pod: $POD_NAME" -ForegroundColor Green
Write-Host ""

# Step 2: Create theme directory in pod
Write-Host "Step 2: Creating theme directory in pod..." -ForegroundColor Yellow
kubectl exec $POD_NAME -n dftp-mcp -- mkdir -p /opt/keycloak/themes/dftp-theme/login/resources/css

# Step 3: Copy theme files
Write-Host "Step 3: Copying theme files to pod..." -ForegroundColor Yellow

# Copy theme.properties
kubectl cp keycloak-theme/dftp-theme/login/theme.properties dftp-mcp/${POD_NAME}:/opt/keycloak/themes/dftp-theme/login/theme.properties

# Copy custom CSS
kubectl cp keycloak-theme/dftp-theme/login/resources/css/custom-theme.css dftp-mcp/${POD_NAME}:/opt/keycloak/themes/dftp-theme/login/resources/css/custom-theme.css

Write-Host "Theme files copied successfully!" -ForegroundColor Green
Write-Host ""

# Step 4: Restart Keycloak to load new theme
Write-Host "Step 4: Restarting Keycloak pod..." -ForegroundColor Yellow
kubectl delete pod $POD_NAME -n dftp-mcp

Write-Host ""
Write-Host "Waiting for Keycloak to restart..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=keycloak -n dftp-mcp --timeout=120s

Write-Host ""
Write-Host "=====================================" -ForegroundColor Green
Write-Host "Theme Deployment Complete!" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Go to Keycloak Admin Console:" -ForegroundColor Yellow
Write-Host "   http://afa63dbe5d4c642fa8cbdd41dbbed252-962611e46584bf7f.elb.us-east-2.amazonaws.com/admin" -ForegroundColor White
Write-Host ""
Write-Host "2. Login with admin credentials (check k8s/keycloak.yaml for password)" -ForegroundColor Yellow
Write-Host ""
Write-Host "3. Go to: Realm Settings > Themes tab" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Set Login Theme to: dftp-theme" -ForegroundColor Yellow
Write-Host ""
Write-Host "5. Click Save" -ForegroundColor Yellow
Write-Host ""
Write-Host "6. Test login at your frontend!" -ForegroundColor Yellow
