# Trade Processing System

## Quick Start

### 1. Start All Services
```bash
start-all-services.bat
```

### 2. Test API
Open: http://localhost:8080/swagger-ui.html

### 3. Monitor Messages
Open: http://localhost:8161/admin (admin/admin)

## Current Issue Fix

**Problem**: Only Trade Capture service is running. Other services need to be started.

**Solution**: 
1. Kill all Java processes: `taskkill /f /im java.exe`
2. Run: `start-all-services.bat`
3. Wait 3-5 minutes for all services to start
4. Check ActiveMQ console - all queues should have consumers

## Expected Queue Status
```
TRADE.RECEIVED   → 0 pending, 2 consumers (Rule + Fraud)
RULE.RESULT      → 0 pending, 1 consumer (Trade Capture)
FRAUD.RESULT     → 0 pending, 1 consumer (Trade Capture)
TRADE.FINAL      → 0 pending, 1 consumer (ACK Service)
```

## Architecture
See: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)

## Files
- `start-all-services.bat` - Start all microservices
- `docker-compose.yml` - ActiveMQ container
- `SYSTEM_ARCHITECTURE.md` - Complete documentation