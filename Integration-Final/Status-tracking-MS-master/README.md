# Status Tracking Microservice

A Spring Boot microservice that consumes status messages from Redis streams and tracks order state history in PostgreSQL database.

## Features

- **Redis Stream Consumer**: Consumes messages from `status-stream`
- **PostgreSQL Integration**: Stores order state history
- **Redis Sentinel**: High availability Redis setup
- **Docker Compose**: Complete containerized environment
- **Flexible Message Processing**: Supports fileId, orderId, and mqid based messages

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Git

### Setup and Run

1. **Clone the repository**
   ```bash
   git clone https://github.com/DFTP-CH/Status-tracking-MS.git
   cd Status-tracking-MS
   ```

2. **Start the application**
   ```bash
   docker compose up -d
   ```

3. **Verify services are running**
   ```bash
   docker ps
   ```

## Architecture

- **Spring Boot Application**: Main microservice
- **PostgreSQL**: Database for order state history
- **Redis Master-Replica**: Stream processing with high availability
- **Redis Sentinel**: Automatic failover management

## Message Format

The service accepts JSON messages with the following structure:

### Required Fields
- `sourceservice`: Source service name
- `status`: Current status

### Message Types

#### 1. Trade-Capture Service (fileId required)
```json
{
  "fileId": "FILE001",
  "sourceservice": "trade-capture",
  "status": "RECEIVED"
}
```

#### 2. Order-based Services (orderId + distributor_id required when no fileId/mqid)
```json
{
  "orderId": "ORDER123",
  "distributor_id": "DIST001",
  "fileid":"F123",
  "sourceservice": "order-service",
  "status": "RECEIVED"
}
```

#### 3. MQID-based Messages
```json
{
  "fileid": null,
  "orderId": "ORDER1234",
  "distributor_id": "DIST001",
  "sourceservice": "some-service",
  "status": "RECEIVED"
}
```

## Testing

### Send Test Messages
```bash
# Trade-capture message
docker exec redis-master redis-cli XADD status-stream "*" payload '{"fileId":"FILE001","sourceservice":"trade-capture","status":"RECEIVED","distributor_id":"123M"}'

# Order-based message
docker exec redis-master redis-cli XADD status-stream "*" payload '{"orderId":"ORDER123","distributor_id":"DIST001","fileid":"F123",sourceservice":"order-service","status":"PROCESSING"}'

# MQID-based message
docker exec redis-master redis-cli XADD status-stream "*" payload '{"fileId":"null","sourceservice":"trade-capture","status":"RECEIVED","distributor_id":"123M"}'
```

### Check Application Logs
```bash
docker logs status-tracking-app --tail 50
```

### Verify Database Records
```bash
docker exec postgres psql -U postgres -d status_track -c "SELECT id, file_id, order_id, distributor_id, mqid, current_state, source_service, event_time FROM order_state_history ORDER BY id DESC LIMIT 20;"
```

## Configuration

### Database Configuration
- **Host**: postgres:5432
- **Database**: status_track
- **Username**: postgres
- **Password**: password

### Redis Configuration
- **Master**: redis-master:6379
- **Sentinels**: sentinel1:26379, sentinel2:26379, sentinel3:26379
- **Stream**: status-stream
- **Consumer Group**: status-group

## Development

### Run Tests
```bash
mvn test
```

### Build Application
```bash
mvn clean package
```

## Monitoring

### Check Redis Stream
```bash
docker exec redis-master redis-cli XRANGE status-stream - +
```

### Check Sentinel Status
```bash
docker exec sentinel1 redis-cli -p 26379 SENTINEL masters
```

### Check Master Address
```bash
docker exec sentinel1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

---

## Developer Notes

<details>
<summary>Click to expand developer commands and testing scenarios</summary>

### Ready-to-run Docker Commands for Testing

Run unit tests:
```bash
mvn test -Dtest=StatusStreamConsumerTest
```

### Sample Message Commands

Trade-capture with fileId:
```bash
docker exec redis-master redis-cli XADD status-stream "*" payload "{\"fileId\":\"FILE001\",\"sourceservice\":\"trade-capture\",\"status\":\"RECEIVED\"}"
```

Trade-capture with orderId (no fileId):
```bash
docker exec redis-master redis-cli XADD status-stream "*" payload "{\"orderId\":\"ORDER123\",\"sourceservice\":\"trade-capture\",\"status\":\"RECEIVED\"}"
```

Other service (no fileId path; requires orderId + distributorId):
```bash
docker exec redis-master redis-cli XADD status-stream "*" payload "{\"orderId\":\"ORDER123\",\"distributor_id\":42,\"sourceservice\":\"order-service\",\"status\":\"COMPLETED\"}"
```

Other service with fileId (file must already exist in DB):
```bash
docker exec redis-master redis-cli XADD status-stream "*" payload "{\"fileId\":\"FILE001\",\"orderId\":\"ORDER123\",\"distributor_id\":42,\"sourceservice\":\"order-service\",\"status\":\"PROCESSING\"}"
```

### Post Docker UP Process

Check sentinel master address:
```bash
docker exec sentinel1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

Sample data insertion:
```bash
docker exec redis-master redis-cli XADD status-stream "*" payload '{"fileId":"FILE001","sourceservice":"trade-capture","status":"PROCESSING"}'
docker exec redis-master redis-cli XADD status-stream "*" payload '{"fileId":"FILE002","order_id":"ORDER123","distributor_id":"DIST001","sourceservice":"order-service","status":"COMPLETED"}'
```

### Monitoring Commands

Check application logs:
```bash
docker logs status-tracking-app --tail 100
```

Query database:
```bash
docker exec postgres psql -U postgres -d status_track -c "SELECT * FROM order_state_history ORDER BY id DESC LIMIT 20;"
```

Add column (if needed):
```bash
docker exec postgres psql -U postgres -d status_track -c "ALTER TABLE order_state_history ADD COLUMN mqid VARCHAR;"
```

### Stream and Group Info

Check data in stream:
```bash
docker exec redis-master redis-cli XRANGE status-stream - +
```

### Network Debugging

Check all IPs:
```bash
docker inspect -f "{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}" redis-master redis-replica1 redis-replica2
```

Check sentinel status:
```bash
docker exec sentinel1 redis-cli -p 26379 SENTINEL masters
```

### Redis Testing

Enter data into redis-master:
```bash
docker exec redis-master redis-cli SET testkey value1
```

View data in replica:
```bash
docker exec redis-replica1 redis-cli GET testkey
docker exec redis-replica2 redis-cli GET testkey
```

### Failover Testing

Stop master:
```bash
docker pause redis-master
```

Check replica role:
```bash
docker exec redis-replica1 redis-cli INFO replication
```

Check changed master:
```bash
docker exec sentinel1 redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster
```

### Stream Operations

```bash
docker exec -it redis-master redis-cli
xrange mystream - +
xlen mystream
xinfo groups mystream
xpending mystream mygroup
```

### Data Testing and Verification

Push data and check DB:
```bash
docker exec redis-master redis-cli XADD status-stream "*" payload '{"fileId":"FUND001","sourceservice":"trade-capture","status":"RECEIVED"}'
```

Check consumption logs:
```bash
docker logs status-tracking-app --tail 50 | findstr /R "New message|Record ID|Data:|ACK SENT|order_state"
```

Check database:
```bash
docker exec postgres psql -U postgres -d status_track -c "SELECT id, file_id, order_id, distributor_id, mqid, current_state, source_service, event_time FROM order_state_history ORDER BY id DESC LIMIT 20;"
```

### JSON Payload Format Rules

⚠️ **IMPORTANT**: Either fileId OR mqid MUST be present (one is required). If neither is present, the message will be skipped.

#### 1. Trade-Capture Service (with fileId)
```
fileId: (required - either fileId or mqid must be present)
sourceservice: "trade-capture"
status: (required)
```

#### 2. Other Services (with fileId or order_id + distributor_id)
```
fileId: (optional - either fileId or mqid must be present)
order_id: (required when fileId and mqid both absent)
distributor_id: (required when fileId and mqid both absent)
sourceservice: (required)
status: (required)
```

#### 3. MQID-based Messages (with mqid - no fileId/orderId checks)
```
mqid: (required - either fileId or mqid must be present)
distributor_id or firm_id: (optional, will be converted to distributor_id)
sourceservice: (required)
status: (required)
```

### Complete Environment Cleanup (Windows)

```batch
REM Stop all running containers
for /f "tokens=*" %i in ('docker ps -q') do docker stop %i

REM Remove all containers
for /f "tokens=*" %i in ('docker ps -q -a') do docker rm %i

REM Remove all images
for /f "tokens=*" %i in ('docker images -q') do docker rmi -f %i

REM Remove all volumes (this deletes databases and Redis data)
for /f "tokens=*" %i in ('docker volume ls -q') do docker volume rm %i

REM Remove all networks (except default ones)
for /f "tokens=*" %i in ('docker network ls -q --filter "driver!=bridge" --filter "name!=docker_gwbridge"') do docker network rm %i

REM Final cleanup: prune everything
docker system prune -a --volumes -f
```

</details>