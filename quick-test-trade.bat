@echo off
echo ========================================
echo Quick Trade Test
echo ========================================

echo.
echo Testing trade submission...

curl -X POST http://localhost:8080/trade ^
  -H "Content-Type: application/json" ^
  -d "{\"symbol\":\"TEST\",\"quantity\":100,\"price\":150.50}"

echo.
echo.
echo Getting all trades...

curl http://localhost:8080/trades

echo.
echo.
echo ========================================
echo Test Complete!
echo Check ActiveMQ: http://localhost:8161/admin
echo ========================================