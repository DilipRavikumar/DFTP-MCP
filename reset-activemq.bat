@echo off
echo ========================================
echo Resetting ActiveMQ
echo ========================================

echo.
echo 1. Stopping ActiveMQ...
docker-compose down

echo.
echo 2. Removing old data...
docker volume rm trade-processing-system_activemq_data 2>nul

echo.
echo 3. Starting fresh ActiveMQ...
docker-compose up -d activemq

echo.
echo 4. Waiting for ActiveMQ to start...
timeout /t 10 /nobreak > nul

echo.
echo ========================================
echo ActiveMQ Reset Complete!
echo Access: http://localhost:8161/admin
echo Username: admin
echo Password: admin
echo ========================================
pause