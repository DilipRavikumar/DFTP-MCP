@echo off
echo ========================================
echo Starting All Microservices Independently
echo ========================================

echo.
echo 1. Starting ActiveMQ...
docker-compose up -d activemq

echo.
echo 2. Building all services...
cd trade-capture && mvn clean compile -q && cd ..
cd rule-service && mvn clean compile -q && cd ..
cd fraud-service && mvn clean compile -q && cd ..
cd ack-service && mvn clean compile -q && cd ..

echo.
echo 3. Starting all microservices on different ports...
start "Trade Capture (8080)" cmd /k "cd trade-capture && mvn spring-boot:run"
timeout /t 3 /nobreak > nul

start "Rule Service (8081)" cmd /k "cd rule-service && mvn spring-boot:run"
timeout /t 3 /nobreak > nul

start "Fraud Service (8082)" cmd /k "cd fraud-service && mvn spring-boot:run"
timeout /t 3 /nobreak > nul

start "ACK Service (8083)" cmd /k "cd ack-service && mvn spring-boot:run"

echo.
echo ========================================
echo All Services Starting...
echo ========================================
echo.
echo Trade Capture:  http://localhost:8080/swagger-ui.html
echo Rule Service:   http://localhost:8081/h2-console
echo Fraud Service:  http://localhost:8082/h2-console  
echo ACK Service:    http://localhost:8083/h2-console
echo.
echo ActiveMQ:       http://localhost:8161/admin
echo ========================================

pause