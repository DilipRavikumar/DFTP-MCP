# Canonical Service

A standalone Spring Boot microservice for processing trade files in multiple formats (JSON, XML, CSV) and converting them into a canonical model with PostgreSQL persistence and ActiveMQ messaging.

## 🚀 Features

- **Multi-format Support**: Process JSON, XML, and CSV trade files
- **Canonical Model**: Convert external formats to standardized internal model
- **Data Validation**: Validate trade data before persistence
- **PostgreSQL Storage**: Store canonical trades and outbox events
- **ActiveMQ Integration**: Publish trades to message queue for downstream processing
- **REST API**: RESTful endpoints for file processing and data queries
- **Swagger/OpenAPI**: Interactive API documentation
- **Outbox Pattern**: Event sourcing with outbox table

## 📋 Tech Stack

- **Java 17**
- **Spring Boot 3.2.0**
- **PostgreSQL 15**
- **ActiveMQ**
- **Spring Data JPA**
- **Jackson** (JSON/XML processing)
- **OpenCSV** (CSV parsing)
- **SpringDoc OpenAPI** (Swagger)
- **Docker Compose**

## 🏗️ Architecture

```
File (JSON/XML/CSV)
      ↓
FileLoaderService
      ↓
MapperService
      ↓
ValidatorService
      ↓
Save to PostgreSQL (canonical_trades)
      ↓
Create Outbox Event (outbox_events)
      ↓
Publish to ActiveMQ Queue
      ↓
QueueListener processes message
```

## 📁 Project Structure

```
Can_ser/
├── src/main/java/com/dfpt/canonical/
│   ├── CanonicalServiceApplication.java
│   ├── config/
│   │   ├── ActiveMQConfig.java
│   │   └── OpenAPIConfig.java
│   ├── controller/
│   │   ├── CanonicalController.java
│   │   └── DataQueryController.java
│   ├── dto/
│   │   └── ExternalTradeDTO.java
│   ├── listener/
│   │   └── QueueListenerService.java
│   ├── model/
│   │   ├── CanonicalTrade.java
│   │   └── OutboxEvent.java
│   ├── repository/
│   │   ├── CanonicalTradeRepository.java
│   │   └── OutboxRepository.java
│   └── service/
│       ├── FileLoaderService.java
│       ├── MapperService.java
│       ├── OutboxService.java
│       ├── QueuePublisherService.java
│       └── ValidatorService.java
├── src/main/resources/
│   ├── application.yml
│   └── schema.sql
├── input/
│   ├── orders.json
│   ├── orders.xml
│   └── orders.csv
├── docker-compose.yml
└── pom.xml
```

## 🛠️ Setup & Installation

### Prerequisites

- Java 17 or higher
- Maven 3.6+
- Docker & Docker Compose (optional, for containerized setup)

### 1. Clone the Repository

```bash
git clone https://github.com/palanikalyan/cano_service.git
cd cano_service
```

### 2. Start Dependencies (Using Docker)

```bash
docker-compose up -d
```

This starts:
- **PostgreSQL** on port 5432
- **ActiveMQ** on ports 61616 (JMS) and 8161 (Web Console)

### 3. Build & Run

```bash
mvn clean install
mvn spring-boot:run
```

The application will start on **http://localhost:8085**

## 📊 API Endpoints

### Process Trade Files

```http
POST /canonical/process/{format}
```

Parameters:
- `format`: `json`, `xml`, or `csv`

Example:
```bash
curl -X POST http://localhost:8085/canonical/process/json
```

### Data Query Endpoints

- `GET /canonical/data/trades-with-events` - Get trades with outbox events
- `GET /canonical/data/all-trades` - Get all canonical trades
- `GET /canonical/data/all-events` - Get all outbox events
- `GET /canonical/data/stats` - Get statistics
- `GET /canonical/data/by-transaction-type` - Group by transaction type
- `GET /canonical/data/by-fund-code` - Group by fund code
- `GET /canonical/data/pending-events` - Get pending outbox events

### Swagger UI

Access interactive API documentation:
```
http://localhost:8085/swagger-ui/index.html
```

## 🗄️ Database

### Connection Details

- **Host**: localhost:5432
- **Database**: canonical_db
- **Username**: postgres
- **Password**: root@123

### Schema

See `src/main/resources/schema.sql` for table definitions.

### Query Data

```sql
-- Check all trades
SELECT * FROM canonical_trades ORDER BY created_at DESC;

-- Check all events
SELECT * FROM outbox_events ORDER BY created_at DESC;

-- Join trades with events
SELECT 
    ct.order_id,
    ct.fund_code,
    ct.amount,
    ct.status as trade_status,
    oe.event_type,
    oe.status as event_status
FROM canonical_trades ct
LEFT JOIN outbox_events oe ON ct.id = oe.aggregate_id
ORDER BY ct.created_at DESC;
```

## 📨 ActiveMQ

### Web Console

Access ActiveMQ management console:
```
http://localhost:8161
```

Credentials:
- **Username**: admin
- **Password**: admin

### Queue Details

- **Queue Name**: `canonical.trades.queue`
- **JMS Port**: 61616

## 🧪 Testing

### Sample Input Files

The `input/` directory contains sample files:

**orders.json**
```json
{
  "orderId": "ORD123",
  "fundCode": "HDFC001",
  "investorName": "Ravi Kumar",
  "txnType": "BUY",
  "amount": 5000,
  "units": 50
}
```

**orders.xml**
```xml
<Order>
  <orderId>ORD124</orderId>
  <fundCode>ICICI002</fundCode>
  <investorName>Priya Sharma</investorName>
  <txnType>SELL</txnType>
  <amount>7500</amount>
  <units>75</units>
</Order>
```

**orders.csv**
```csv
orderId,fundCode,investorName,txnType,amount,units
ORD125,SBI003,Amit Patel,BUY,10000,100
```

## 📝 Configuration

Key configuration in `application.yml`:

```yaml
spring:
  datasource:
    url: jdbc:postgresql://localhost:5432/canonical_db
    username: postgres
    password: root@123
  
  activemq:
    broker-url: tcp://localhost:61616
    user: admin
    password: admin

server:
  port: 8085
```

## 🔧 Development

### Build

```bash
mvn clean install
```

### Run Tests

```bash
mvn test
```

### Package

```bash
mvn package
```

## 📚 Documentation

- [ActiveMQ Integration Guide](RABBITMQ_GUIDE.md)
- [Database Queries](database-queries.sql)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License.

## 👤 Author

**Palani Kalyan**
- GitHub: [@palanikalyan](https://github.com/palanikalyan)

## 🙏 Acknowledgments

- Spring Boot team
- Apache ActiveMQ community
- PostgreSQL team
