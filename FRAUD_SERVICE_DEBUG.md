# FRAUD SERVICE DEBUG - Why Fraud Results Are PENDING

## The Problem
All trades show `fraudResult: "PENDING"` while `ruleResult` has actual values.

This means:
- ✅ Rule Service IS working (responding with APPROVE/REJECT)
- ❌ Fraud Service is NOT working (never sending FRAUD.RESULT messages)

## Root Cause Analysis

### Possible Issues:
1. **Fraud Service is not running** - Port 8082 is not listening
2. **Fraud Service is not receiving TRADE.RECEIVED messages** - ActiveMQ connection issue
3. **Fraud Service is receiving but not sending FRAUD.RESULT** - JmsTemplate issue
4. **Exception during message processing** - Exception being thrown silently

## How to Diagnose

### Step 1: Check if Fraud Service is Running
```bash
# Check if service is up on port 8082
curl http://localhost:8082/actuator/health

# Or check process
netstat -ano | findstr :8082
```

### Step 2: Check Service Logs
You should see ONE of these patterns:

**IF WORKING:**
```
===== FRAUD SERVICE LISTENER TRIGGERED =====
Fraud Service received: 1,AAPL,100,150
Fraud Service - Parsed: TradeId=1, Name=AAPL, Qty=100, Price=150.0
Fraud Service - CheckFraud result: APPROVE, RiskScore: 10
Fraud Service - Saved to database: 1
Fraud Service - Published to FRAUD.RESULT: 1,APPROVE
Fraud check for 1: APPROVE
===== FRAUD SERVICE LISTENER COMPLETE =====
```

**IF NOT RECEIVING MESSAGES:**
```
===== FRAUD SERVICE LISTENER TRIGGERED ===== 
(will NOT appear at all)
```

**IF EXCEPTION:**
```
===== FRAUD SERVICE ERROR =====
ERROR: (specific error message here)
```

### Step 3: Check ActiveMQ Console
1. Go to http://localhost:8161/admin
2. Check **Queues** tab
3. You should see:
   - `TRADE.RECEIVED` - messages coming in from Trade Capture
   - `RULE.RESULT` - messages from Rule Service (should be consumed)
   - `FRAUD.RESULT` - messages from Fraud Service (should be consumed)

**Red Flag:** If FRAUD.RESULT queue has no messages but TRADE.RECEIVED has pending messages, Fraud Service isn't processing.

## The Fix

### 1. Verify All Services Are Built
```bash
cd c:\Users\dilip\Documents\Trade-Processing-system
mvn clean package -DskipTests
```

### 2. Start Services in Order
```bash
# Terminal 1: ActiveMQ
cd c:\path\to\activemq
bin\activemq.bat

# Terminal 2: Rule Service
cd c:\Users\dilip\Documents\Trade-Processing-system\rule-service
mvn spring-boot:run

# Terminal 3: Fraud Service
cd c:\Users\dilip\Documents\Trade-Processing-system\fraud-service
mvn spring-boot:run

# Terminal 4: Trade Capture
cd c:\Users\dilip\Documents\Trade-Processing-system\trade-capture
mvn spring-boot:run

# Terminal 5: Ack Service (Optional, but recommended)
cd c:\Users\dilip\Documents\Trade-Processing-system\ack-service
mvn spring-boot:run
```

### 3. Test with Sample Trade
```bash
curl -X POST http://localhost:8080/trade \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"TEST\",\"quantity\":100,\"price\":150.50}"
```

### 4. Check Console Output
Monitor the terminal where Trade Capture and Fraud Service are running:
- You should see FRAUD SERVICE LISTENER TRIGGERED
- You should see "Published to FRAUD.RESULT"

### 5. Query Results
```bash
curl http://localhost:8080/trades
```

All trades should now have proper status (ACK or NACK) instead of PENDING.

## If Still Not Working

Check these files for missing dependencies:
- `fraud-service/pom.xml` - Should have spring-boot-starter-activemq
- `fraud-service/src/main/resources/application.properties` - Should have correct broker URL

Compare with working Rule Service files to ensure they match.
