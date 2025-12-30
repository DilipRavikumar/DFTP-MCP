package com.example.status.service;

import com.fasterxml.jackson.databind.ObjectMapper;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.stream.*;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.beans.factory.annotation.Autowired;
import com.example.status.dao.OrderStateHistoryDao;
import com.example.status.entity.OrderStateHistoryEntity;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.ZoneId;
import org.springframework.data.domain.Range;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.springframework.data.redis.connection.stream.StreamRecords;

@Service
public class StatusStreamConsumer {

    @Autowired
    private StringRedisTemplate redisTemplate;

    private static final int MAX_DELIVERY_ATTEMPTS = 5;

    @Value("${app.redis.stream}")
    private String STREAM_KEY;

    @Value("${app.redis.dlq-stream}")
    private String DLQ_STREAM;

    @Value("${app.redis.group}")
    private String GROUP_NAME;

    @Value("${app.redis.consumer}")
    private String CONSUMER_NAME;

    @Autowired
    private OrderStateHistoryDao historyDao;

     @PostConstruct
    public void initGroup() {
        try {
            redisTemplate.opsForStream().createGroup(STREAM_KEY, GROUP_NAME);
            System.out.println("Consumer group created: " + GROUP_NAME);
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("BUSYGROUP")) {
                System.out.println(" Consumer group already exists: " + GROUP_NAME);
            } else {
                System.err.println(" Failed to create consumer group: " + e.getMessage());
            }
        }
    }

    @Scheduled(fixedDelay = 10000)
    private void startConsuming() {
        System.out.println("Consumer loop started for stream: " + STREAM_KEY + ", group: " + GROUP_NAME);
        
            try {
                StreamOffset<String> offset = StreamOffset.create(STREAM_KEY, ReadOffset.lastConsumed());
                List<MapRecord<String, Object, Object>> messages = redisTemplate.opsForStream().read(
                        Consumer.from(GROUP_NAME, CONSUMER_NAME),
                        StreamReadOptions.empty().count(10).block(Duration.ofSeconds(5)),
                        offset);

                if (messages != null && !messages.isEmpty()) {
                    for (MapRecord<String, Object, Object> message : messages) {
                        handleWithAck(message);
                    }
                }else{
                    System.out.println("No new messages to process");
                    return;
                }

            } catch (Exception e) {
                System.err.println("Error while reading stream: " + e.getMessage());
                
            }
        
    }

   private void handleWithAck(MapRecord<String, Object, Object> message) {
    String recordId = message.getId().getValue();
    Map<Object, Object> data = message.getValue();

    int attempts = 0;
    boolean success = false;

    while (attempts < 3) {
        try {
            attempts++;
            success = writeToDatabase(recordId, data);

            if (success) break;

        } catch (Exception e) {
            System.err.println("DB error attempt " + attempts + " for " + recordId + ": " + e.getMessage());
        }
    }

    if (success) {
        redisTemplate.opsForStream().acknowledge(STREAM_KEY, GROUP_NAME, message.getId());
        redisTemplate.opsForStream().delete(STREAM_KEY, message.getId());
        System.out.println("ACK SENT after " + attempts + " attempts for " + recordId);

    } else {
        System.err.println("FAILED after 3 attempts. Moving to DLQ: " + recordId);
        moveToDlq(message.getId(), attempts, "DB failures");
    }
}


            

    private void moveToDlq(RecordId recordId, long attempts, String reason) {
        try {
            List<MapRecord<String, Object, Object>> original = redisTemplate.opsForStream().range(
                    STREAM_KEY,
                    Range.closed(recordId.getValue(), recordId.getValue()));

            Map<String, Object> dlqPayload = new java.util.HashMap<>();
            dlqPayload.put("failed_record_id", recordId.getValue());
            dlqPayload.put("reason", reason);
            dlqPayload.put("attempts", String.valueOf(attempts));

            if (original != null && !original.isEmpty()) {
                dlqPayload.put("stream_payload", toJson(original.get(0).getValue()));
            }

            redisTemplate.opsForStream().add(StreamRecords.newRecord()
                    .in(DLQ_STREAM)
                    .ofMap(dlqPayload));

            redisTemplate.opsForStream().acknowledge(STREAM_KEY, GROUP_NAME, recordId);
            redisTemplate.opsForStream().delete(STREAM_KEY, recordId);
            System.err.println("Moved record to DLQ after " + attempts + " attempts: " + recordId.getValue());
        } catch (Exception e) {
            System.err.println("Failed to move record to DLQ: " + recordId.getValue() + " because " + e.getMessage());
        }
    }

    private String toJson(Map<Object, Object> map) {
        try {
            return new ObjectMapper().writeValueAsString(map);
        } catch (Exception e) {
            return String.valueOf(map);
        }
    }

    private boolean writeToDatabase(String recordId, Map<Object, Object> data) throws Exception {
        Map<String, Object> payload = parsePayload(data.get("payload"));
        if (payload == null) {
            System.err.println("Payload missing or invalid for record: " + recordId);
            return false;
        }

        String sourceService = getStringValue(payload, "sourceservice", "source_service", "sourceService");
        String status = getStringValue(payload, "status");
        String fileId = getStringValue(payload, "fileId", "files_id", "file_id");
        String orderId = getStringValue(payload, "orderId", "order_id");
        Integer distributorId = getIntValue(payload, "distributorId", "distributor_id", "firmId", "firm_id");

        if (status == null || sourceService == null) {
            System.err.println("Missing status/sourceService for record: " + recordId);
            return false;
        }

        boolean isTradeCapture = "trade-capture".equalsIgnoreCase(sourceService);
        validateIdentifiers(recordId, sourceService, isTradeCapture, fileId, orderId, distributorId);

        LocalDateTime eventTime = extractEventTime(recordId);
        String previousState = findPreviousState(fileId, orderId, distributorId);

        OrderStateHistoryEntity entity = new OrderStateHistoryEntity();
        entity.setFileId(fileId);
        entity.setOrderId(orderId);
        entity.setDistributorId(distributorId);
        entity.setPreviousState(previousState);
        entity.setCurrentState(status);
        entity.setSourceService(sourceService);
        entity.setEventTime(eventTime);

        historyDao.save(entity);

        System.out.println("Saved to DB: fileId=" + fileId +
                " orderId=" + orderId +
                " [distributor=" + distributorId + "] : " +
                previousState + " -> " + status +
                " (source: " + sourceService + ")");

        return true;
    }

  private Map<String, Object> parseSimpleKeyValueString(String str) {
        Map<String, Object> map = new java.util.HashMap<>();
        if (str == null) return map;
        String cleaned = str.replaceAll("[{}]", "").trim();
        if (cleaned.isEmpty()) return map;
        for (String pair : cleaned.split(",")) {
            String[] kv = pair.split(":", 2);
            if (kv.length == 2) {
                map.put(kv[0].trim(), kv[1].trim());
            }
        }
        return map;
    }

    private Map<String, Object> parsePayload(Object payloadObj) {
        if (payloadObj == null) {
            return null;
        }
         Map<String, Object> payloadMap = new java.util.HashMap<>();
        if (payloadObj instanceof Map) {
            Map<Object, Object> rawMap = (Map<Object, Object>) payloadObj;
            for (Map.Entry<Object, Object> entry : rawMap.entrySet()) {
                payloadMap.put(String.valueOf(entry.getKey()), entry.getValue());
            }
            return payloadMap;
        }
        String payloadStr = (payloadObj instanceof String)
            ? (String) payloadObj
            : payloadObj.toString();
        ObjectMapper objectMapper = new ObjectMapper();
        try {
            payloadMap = objectMapper.readValue(payloadStr, Map.class);
            return payloadMap;
        } catch (Exception ex) {
            System.out.println("JSON parse failed, fallback for: " + payloadStr);
            Map<String, Object> fallback = parseSimpleKeyValueString(payloadStr);
            return fallback.isEmpty() ? null : fallback;
        }
    }

    private void validateIdentifiers(String recordId, String sourceService, boolean isTradeCapture,
            String fileId, String orderId, Integer distributorId) {
        if (isTradeCapture) {
            if (fileId == null && orderId == null) {
                throw new IllegalStateException("trade-capture requires orderId or fileId (" + recordId + ")");
            }
            return;
        }

        if (orderId == null || distributorId == null) {
            throw new IllegalStateException("orderId and distributorId are required for service "
                    + sourceService + " (" + recordId + ")");
        }

        if (fileId == null) {
            if (historyDao.findTopByOrderIdOrderByEventTimeDesc(orderId).isEmpty()) {
                throw new IllegalStateException("orderId " + orderId + " not seen yet from trade-capture ("
                        + recordId + ")");
            }
        } else if (!historyDao.existsByFileId(fileId)) {
            throw new IllegalStateException("fileId " + fileId + " not found yet for order: " + orderId
                    + " (" + recordId + ")");
        }
    }

    private LocalDateTime extractEventTime(String recordId) {
        String timestampPart = recordId.split("-")[0];
        long timestampMillis = Long.parseLong(timestampPart);
        return Instant.ofEpochMilli(timestampMillis)
                .atZone(ZoneId.systemDefault())
                .toLocalDateTime();
    }

    private String findPreviousState(String fileId, String orderId, Integer distributorId) {
        Optional<OrderStateHistoryEntity> lastRecord = Optional.empty();
        if (fileId != null) {
            lastRecord = historyDao.findTopByFileIdOrderByEventTimeDesc(fileId);
        } else if (orderId != null && distributorId != null) {
            lastRecord = historyDao.findTopByOrderIdAndDistributorIdOrderByEventTimeDesc(orderId, distributorId);
            if (lastRecord.isEmpty()) {
                lastRecord = historyDao.findTopByOrderIdOrderByEventTimeDesc(orderId);
            }
        } else if (orderId != null) {
            lastRecord = historyDao.findTopByOrderIdOrderByEventTimeDesc(orderId);
        }
        return lastRecord.map(OrderStateHistoryEntity::getCurrentState).orElse(null);
    }

    private String getStringValue(Map<String, Object> map, String... fieldNames) {
        if (map == null || fieldNames == null || fieldNames.length == 0) {
            return null;
        }

        for (String fieldName : fieldNames) {
            Object value = map.get(fieldName);
            if (value != null) {
                String strValue = String.valueOf(value).trim();
                if (!strValue.isEmpty() && !"null".equalsIgnoreCase(strValue)) {
                    return strValue;
                }
            }
        }
        return null;
    }

    private Integer getIntValue(Map<String, Object> map, String... fieldNames) {
        String value = getStringValue(map, fieldNames);
        if (value == null) {
            return null;
        }
        try {
            return Integer.valueOf(value);
        } catch (NumberFormatException e) {
            System.err.println("Failed to parse integer from value '" + value + "'");
            return null;
        }
    }

}