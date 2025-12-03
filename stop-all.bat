@echo off
echo ========================================
echo Stopping All Services
echo ========================================

echo.
echo 1. Stopping all Java processes...
taskkill /f /im java.exe 2>nul

echo.
echo 2. Stopping ActiveMQ...
docker-compose down

echo.
echo ========================================
echo All services stopped!
echo ========================================