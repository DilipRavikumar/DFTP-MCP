@echo off
REM Quick test with detailed output

echo ========================================
echo Testing Trade Processing System
echo ========================================
echo.

echo Submitting 4 test trades...
echo.

curl -X POST http://localhost:8080/trade ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"AAPL\",\"quantity\":100,\"price\":150}"

timeout /t 2

curl -X POST http://localhost:8080/trade ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"GOOGL\",\"quantity\":50,\"price\":2500}"

timeout /t 2

curl -X POST http://localhost:8080/trade ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"MSFT\",\"quantity\":-10,\"price\":300}"

timeout /t 2

curl -X POST http://localhost:8080/trade ^
  -H "Content-Type: application/json" ^
  -d "{\"name\":\"BNY\",\"quantity\":100,\"price\":150.5}"

timeout /t 3

echo.
echo ========================================
echo Fetching Results...
echo ========================================
echo.

curl http://localhost:8080/trades

echo.
echo.
echo ========================================
echo Test Complete!
echo ========================================
echo.
echo Expected Results:
echo - All trades should have status = ACK or NACK (not RECEIVED)
echo - All trades should have ruleResult = APPROVE or REJECT (not PENDING)
echo - All trades should have fraudResult = APPROVE or REJECT (not PENDING)
echo.
echo If fraudResult is still PENDING:
echo 1. Check the "Fraud Service" terminal window for errors
echo 2. Look for "===== FRAUD SERVICE LISTENER TRIGGERED =====" message
echo 3. Check ActiveMQ console: http://localhost:8161/admin
echo.
