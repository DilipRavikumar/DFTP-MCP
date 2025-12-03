@echo off
echo ========================================
echo Clean Start - All Services
echo ========================================

echo.
echo 1. Stopping everything...
taskkill /f /im java.exe 2>nul
docker-compose down

echo.
echo 2. Cleaning ActiveMQ data...
docker volume rm trade-processing-system_activemq_data 2>nul

echo.
echo 3. Starting ActiveMQ...
docker-compose up -d activemq
timeout /t 10 /nobreak > nul

echo.
echo 4. Building all services...
cd trade-capture && mvn clean compile -q && cd ..
cd rule-service && mvn clean compile -q && cd ..
cd fraud-service && mvn clean compile -q && cd ..
cd ack-service && mvn clean compile -q && cd ..

echo.
echo 5. Starting all microservices...
start "Trade Capture (8080)" cmd /k "cd trade-capture && mvn spring-boot:run"
timeout /t 3 /nobreak > nul

start "Rule Service (8081)" cmd /k "cd rule-service && mvn spring-boot:run"
timeout /t 3 /nobreak > nul

start "Fraud Service (8082)" cmd /k "cd fraud-service && mvn spring-boot:run"
timeout /t 3 /nobreak > nul

start "ACK Service (8083)" cmd /k "cd ack-service && mvn spring-boot:run"

echo.
echo ========================================
echo Clean Start Complete!
echo ========================================
echo.
echo Access Points:
echo Trade API: http://localhost:8080/swagger-ui.html
echo ActiveMQ:  http://localhost:8161/admin
echo ========================================