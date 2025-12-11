# DFTP Integration Project Overview

## 📋 Project Summary
This is a **Distributed Trade File Processing (DFTP)** system - a microservices-based architecture for processing trade files, converting them to canonical format, publishing events, and tracking order status across multiple systems.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DFTP System Architecture                │
└─────────────────────────────────────────────────────────────┘

1. Trade File Input (Multiple Formats)
   └─> JSON/XML/CSV

2. Canonical Service (Can_ser)
   └─> File Processing → Validation → PostgreSQL Storage
       └─> ActiveMQ Queue Publishing

3. Central Event Publisher (Central-Event-Publisher-central)
   └─> Event aggregation and publishing

4. Status Tracking Service (Status-tracking-MS-master)
   └─> Redis Streams Consumer → PostgreSQL Order State History
   └─> High Availability with Redis Sentinel

5. Trade Simulator (Trade-Simulator-main)
   └─> Generates test trade data

6. DFTP Core (dftp)
   └─> Core business logic
```

---

## 📁 Microservices Breakdown

### 1. **Can_ser (Canonical Service)**
**Purpose**: Multi-format file processing and canonical data conversion

**Location**: `C:\DFTP-Final\Integration-Final\Can_ser`

**Tech Stack**:
- Java 17
- Spring Boot 3.2.0
- PostgreSQL 15
- ActiveMQ
- Spring Data JPA
- Jackson (JSON/XML)
- OpenCSV (CSV)
- Swagger/OpenAPI

**Key Components**:
```
src/main/java/com/dfpt/canonical/
├── controller/
│   ├── CanonicalController.java       - REST endpoints
│   └── DataQueryController.java       - Data query endpoints
├── service/
│   ├── FileLoaderService.java         - File loading
│   ├── MapperService.java             - Format conversion
│   ├── ValidatorService.java          - Data validation
│   ├── QueuePublisherService.java     - ActiveMQ publishing
│   └── OutboxService.java             - Event outbox
├── model/
│   ├── CanonicalTrade.java            - Core trade model
│   └── OutboxEvent.java               - Event model
├── repository/
│   ├── CanonicalTradeRepository.java
│   └── OutboxRepository.java
└── config/
    ├── ActiveMQConfig.java
    └── OpenAPIConfig.java
```

**Database Tables**:
- `canonical_trades` - Processed trades
- `outbox_events` - Event sourcing

**Ports**: 
- Application: 8080
- ActiveMQ: 61616

---

### 2. **Status-tracking-MS-master (Status Tracking Service)**
**Purpose**: Track order/file status changes across services

**Location**: `C:\DFTP-Final\Integration-Final\Status-tracking-MS-master`

**Tech Stack**:
- Java 17
- Spring Boot 3.5.8
- PostgreSQL
- Redis 7 (Master-Replica setup)
- Redis Sentinel (3 instances for HA)
- Spring Data Redis

**Key Components**:
```
src/main/java/com/example/status/
├── service/
│   └── StatusStreamConsumer.java      - Redis stream consumer
├── entity/
│   └── OrderStateHistoryEntity.java   - Order state history
├── dao/
│   └── OrderStateHistoryDao.java      - Data access
└── config/
    └── RedisConfig.java               - Redis configuration
```

**Redis Configuration**:
- **Redis Master**: Port 6379
- **Redis Replica 1**: Port 6380
- **Redis Replica 2**: Port 6381
- **Sentinel 1**: Port 26379
- **Sentinel 2**: Port 26380
- **Sentinel 3**: Port 26381

**Stream Processing**:
- Stream: `status-stream`
- Consumer Group: `test-group`
- Message Format: JSON with payload field

**Message Types Supported**:
1. **Trade-Capture**: Requires `fileId`
2. **Order-based**: Requires `orderId` + `distributor_id`
3. **MQID-based**: Flexible identifiers

**Database**:
- `order_state_history` - Order status tracking

**Port**: 8085

---

### 3. **Central-Event-Publisher-central (Event Publisher)**
**Purpose**: Centralized event publishing

**Location**: `C:\DFTP-Final\Integration-Final\Central-Event-Publisher-central`

**Tech Stack**:
- Java 17
- Spring Boot 3.3.4
- Event publishing framework

**Status**: Configuration fixed (Spring Boot version corrected)

---

### 4. **Trade-Simulator-main**
**Purpose**: Generate test trade data for system testing

**Location**: `C:\DFTP-Final\Integration-Final\Trade-Simulator-main`

**Tech Stack**:
- Java 17
- Spring Boot 3.2.2
- SFTP support (JSch)
- File generation utilities

**Key Features**:
- Generates test orders
- SFTP client for file transfer
- Trade data simulation

---

### 5. **dftp (Core Module)**
**Purpose**: Core DFTP business logic

**Location**: `C:\DFTP-Final\Integration-Final\dftp`

**Tech Stack**:
- Java 17
- Spring Boot 3.5.8
- PostgreSQL
- Spring Data JPA

---

## 🔄 Data Flow

```
Trade Files (JSON/XML/CSV)
        ↓
[Can_ser - Canonical Service]
        ↓
    Validation
        ↓
PostgreSQL (canonical_trades)
        ↓
Outbox Events Created
        ↓
ActiveMQ Queue Published
        ↓
[Status Tracking Service]
        ↓
Redis Streams (status-stream)
        ↓
PostgreSQL (order_state_history)
        ↓
Order Status History Maintained
```

---

## 🐳 Docker Configuration

### Can_ser Services
- postgres (port 5432)
- activemq (port 61616, 8161 console)
- canonical-service-app (port 8080)

### Status-tracking-MS-master Services
- postgres (port 5432)
- redis-master (port 6379)
- redis-replica1 (port 6380)
- redis-replica2 (port 6381)
- sentinel1, sentinel2, sentinel3 (ports 26379-26381)
- status-tracking-app (port 8085)

---

## 🔧 Build & Deployment

### Build All Services
```bash
# Can_ser
cd Can_ser && mvn clean install

# dftp
cd dftp && mvn clean install

# Central-Event-Publisher-central
cd Central-Event-Publisher-central && mvn clean install

# Trade-Simulator-main
cd Trade-Simulator-main && mvn clean install

# Status-tracking-MS-master
cd Status-tracking-MS-master && mvn clean install
```

### Docker Deployment
```bash
# Can_ser
docker compose -f Can_ser/docker-compose.yml up -d --build

# Status-tracking-MS-master
docker compose -f Status-tracking-MS-master/docker-compose.yml up -d --build
```

---

## 📊 Database Schema

### Canonical Service (PostgreSQL)
```sql
canonical_trades
├── id
├── order_id
├── file_id
├── trade_data
├── created_at
└── updated_at

outbox_events
├── id
├── aggregate_id
├── event_type
├── payload
├── published
└── created_at
```

### Status Tracking Service (PostgreSQL)
```sql
order_state_history
├── id
├── file_id
├── order_id
├── distributor_id
├── previous_state
├── current_state
├── source_service
├── event_time
└── created_at
```

---

## 🧪 Testing

### Send Test Messages to Redis Stream
```bash
# Trade-capture message
docker exec redis-master redis-cli XADD status-stream "*" \
  payload '{"fileId":"FILE001","sourceservice":"trade-capture","status":"RECEIVED"}'

# Order-based message
docker exec redis-master redis-cli XADD status-stream "*" \
  payload '{"orderId":"ORDER123","distributor_id":"DIST001","sourceservice":"order-service","status":"PROCESSING"}'
```

### Check Application Logs
```bash
docker logs status-tracking-app
docker logs canonical-service-app
```

---

## 🚀 Current Status

| Service | Status | Port | Notes |
|---------|--------|------|-------|
| Can_ser | ✅ Built | 8080 | Multi-format file processing |
| Status-tracking-MS-master | ✅ Running | 8085 | Redis stream consumer, fixed test failure |
| Central-Event-Publisher | ✅ Built | - | Event publishing |
| Trade-Simulator | ✅ Built | - | Test data generator |
| dftp | ✅ Built | - | Core logic |

**Recent Fixes**:
- Fixed deprecated `@MockBean` usage in Status-tracking-MS-master tests
- Fixed `parsePayload` method to return `null` for invalid JSON instead of empty map
- All test cases now passing (11/11)

---

## 📝 Key Integration Points

1. **Canonical Service → Message Queue**: Uses ActiveMQ to publish canonical trades
2. **Message Queue → Status Service**: Events trigger status updates
3. **Redis Streams**: Status service consumes from Redis streams with consumer groups
4. **PostgreSQL**: Persistent storage for both canonical data and status history
5. **Redis Sentinel**: High availability for Redis infrastructure

---

## 🔐 Security Considerations

- PostgreSQL credentials in environment variables
- Redis password configuration available
- ActiveMQ security configuration
- API authentication should be configured for production

---

## 📚 Documentation Files

- `Can_ser/README.md` - Canonical Service documentation
- `Status-tracking-MS-master/README.md` - Status Tracking documentation
- Migration scripts in respective service directories

---

## 🎯 Next Steps for Development

1. Configure cross-service communication
2. Implement end-to-end testing
3. Set up monitoring and logging aggregation
4. Configure API authentication/authorization
5. Performance testing with load generation
6. Production deployment configuration
