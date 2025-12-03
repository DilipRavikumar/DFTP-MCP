# Trade Processing System - Architecture & Flow

## Overview
Asynchronous microservice-based trade processing system that handles trades through business rule validation and fraud detection with guaranteed delivery using ActiveMQ message broker.

## System Architecture

```
CLIENT → TRADE CAPTURE (8080) → ActiveMQ → RULE SERVICE (8081)
                ↓                              ↓
         DATABASE (H2)                   DATABASE (H2)
                ↓                              ↓
         TRADE.RECEIVED ←────────────────── RULE.RESULT
                ↓
         FRAUD SERVICE (8082) ←─────── TRADE.RECEIVED
                ↓
         DATABASE (H2)
                ↓
         FRAUD.RESULT ──→ TRADE CAPTURE (combines results)
                                ↓
                         TRADE.FINAL ──→ ACK SERVICE (8083)
                                              ↓
                                       DATABASE (H2)
                                              ↓
                                       REST /ack ──→ TRADE CAPTURE
```

## Microservices

| Service | Port | Database | Purpose |
|---------|------|----------|---------|
| **Trade Capture** | 8080 | `tradedb` | Entry point, aggregator, REST API |
| **Rule Service** | 8081 | `ruledb` | Business validation logic |
| **Fraud Service** | 8082 | `frauddb` | Fraud detection & ML checks |
| **ACK Service** | 8083 | `ackdb` | Confirmation delivery |

## Message Flow

### 1. Trade Submission
```
POST /trade → Trade Capture → Save to DB → Publish TRADE.RECEIVED
```

### 2. Parallel Processing
```
TRADE.RECEIVED → Rule Service → Business Validation → RULE.RESULT
TRADE.RECEIVED → Fraud Service → Fraud Detection → FRAUD.RESULT
```

### 3. Result Aggregation
```
Trade Capture ← RULE.RESULT + FRAUD.RESULT → Combine → TRADE.FINAL
```

### 4. Acknowledgment
```
TRADE.FINAL → ACK Service → REST /ack → Trade Capture → Final Status
```

## ActiveMQ Queues

| Queue Name | Producer | Consumer | Purpose |
|------------|----------|----------|---------|
| `TRADE.RECEIVED` | Trade Capture | Rule + Fraud Services | Initial trade distribution |
| `RULE.RESULT` | Rule Service | Trade Capture | Business validation results |
| `FRAUD.RESULT` | Fraud Service | Trade Capture | Fraud detection results |
| `TRADE.FINAL` | Trade Capture | ACK Service | Final processing results |

## Business Logic

### Rule Service Validation
- Quantity > 0
- Price > 0  
- Symbol length >= 2

### Fraud Service Detection
- Quantity <= 10,000 (high volume check)
- Price <= 5,000 (high value check)

### Final Decision
```
IF (Rule = APPROVE AND Fraud = APPROVE) 
   THEN Final = ACK
   ELSE Final = NACK
```

## Database Schema

### Trade Capture (tradedb)
```sql
trades: id, symbol, quantity, price, status, timestamp
outbox_events: id, event_type, payload, status
```

### Rule Service (ruledb)
```sql
rule_results: id, trade_id, result, reason, timestamp
outbox_events: id, event_type, payload, status
```

### Fraud Service (frauddb)
```sql
fraud_results: id, trade_id, result, risk_score, timestamp
outbox_events: id, event_type, payload, status
```

### ACK Service (ackdb)
```sql
ack_logs: id, trade_id, status, delivery_time, timestamp
outbox_events: id, event_type, payload, status
```

## Reliability Features

### Safe Store Pattern (Outbox)
- All outgoing messages stored in database before publishing
- Background scheduler retries failed messages
- Ensures no message loss even during failures

### Guaranteed Delivery
- Mandatory REST /ack callback from ACK Service
- Persistent message queues in ActiveMQ
- Database transactions for consistency

### Fault Tolerance
- Each service has independent database
- Services can restart without data loss
- Message replay capability through outbox pattern

## API Documentation

### REST Endpoints

#### Trade Submission
```http
POST /trade
Content-Type: application/json

{
  "symbol": "AAPL",
  "quantity": 100,
  "price": 150.50
}

Response: {"status": "RECEIVED"}
```

#### Swagger UI
```
http://localhost:8080/swagger-ui.html
```

## Technology Stack

- **Framework**: Spring Boot 3.1.0
- **Message Broker**: Apache ActiveMQ
- **Database**: H2 (in-memory)
- **ORM**: JPA/Hibernate
- **API Documentation**: Swagger/OpenAPI 3
- **Build Tool**: Maven
- **Java Version**: 17

## Running the System

### Prerequisites
- Java 17+
- Maven 3.6+
- Docker (for ActiveMQ)

### Start All Services
```bash
start-all-services.bat
```

### Access Points
- **API Testing**: http://localhost:8080/swagger-ui.html
- **ActiveMQ Console**: http://localhost:8161/admin (admin/admin)
- **Database Consoles**: 
  - Trade: http://localhost:8080/h2-console
  - Rule: http://localhost:8081/h2-console
  - Fraud: http://localhost:8082/h2-console
  - ACK: http://localhost:8083/h2-console

## Testing

### Sample Trade Request
```json
{
  "symbol": "AAPL",
  "quantity": 100,
  "price": 150.50
}
```

### Expected Flow
1. Trade submitted via Swagger UI
2. Check ActiveMQ queues for message flow
3. Verify database entries in each service
4. Confirm final ACK/NACK response

## Scalability

- **Horizontal**: Multiple instances of each service
- **Vertical**: Increase JVM heap size
- **Message Concurrency**: Configurable thread pools
- **Database**: Switch to production databases (PostgreSQL/MySQL)

## Production Considerations

- Replace H2 with production databases
- Configure ActiveMQ clustering
- Add monitoring and logging
- Implement circuit breakers
- Add authentication/authorization
- Configure load balancers