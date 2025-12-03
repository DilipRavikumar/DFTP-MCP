@echo off
REM Start all services with detailed logging for debugging

echo ========================================
echo Building all services...
echo ========================================

cd c:\Users\dilip\Documents\Trade-Processing-system

echo Cleaning and building trade-capture...
cd trade-capture
call mvn clean package -DskipTests
cd ..

echo Cleaning and building rule-service...
cd rule-service
call mvn clean package -DskipTests
cd ..

echo Cleaning and building fraud-service...
cd fraud-service
call mvn clean package -DskipTests
cd ..

echo Cleaning and building ack-service...
cd ack-service
call mvn clean package -DskipTests
cd ..

echo.
echo ========================================
echo Starting Services - FOLLOW THE OUTPUT!
echo ========================================
echo.

REM Start ActiveMQ first (assuming it's running or will be started separately)
echo ActiveMQ should be running on tcp://localhost:61616
echo.

REM Now start the services with debugging
timeout /t 3

cd c:\Users\dilip\Documents\Trade-Processing-system

start "Rule Service" cmd /k "cd rule-service && echo Starting Rule Service on port 8081... && mvn spring-boot:run"
timeout /t 5

start "Fraud Service" cmd /k "cd fraud-service && echo Starting Fraud Service on port 8082... && mvn spring-boot:run"
timeout /t 5

start "Trade Capture" cmd /k "cd trade-capture && echo Starting Trade Capture on port 8080... && mvn spring-boot:run"
timeout /t 5

start "Ack Service" cmd /k "cd ack-service && echo Starting Ack Service on port 8083... && mvn spring-boot:run"

echo.
echo ========================================
echo Services Started!
echo ========================================
echo.
echo Access:
echo - Trade Capture API: http://localhost:8080
echo - Rule Service: http://localhost:8081
echo - Fraud Service: http://localhost:8082
echo - Ack Service: http://localhost:8083
echo - ActiveMQ Console: http://localhost:8161/admin
echo.
echo Watch the terminal windows for startup messages and errors.
echo Look for "===== FRAUD SERVICE LISTENER TRIGGERED =====" to confirm Fraud Service is receiving messages.
echo.
