package com.dftp.Service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.stream.RecordId;
import org.springframework.data.redis.connection.stream.StreamRecords;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class StatusTrackingService {

    private final StringRedisTemplate redisTemplate;

    @Value("${app.redis.stream:status-stream}")
    private String streamKey;

    public String sendStatusMessage(UUID rawOrderId, String source, String status) {
        try {
            Map<String, String> payload = new HashMap<>();
            

            if ("MQ".equalsIgnoreCase(source)) {
                payload.put("orderId", rawOrderId.toString());
            } else if ("S3".equalsIgnoreCase(source)) {
                payload.put("fileId", rawOrderId.toString());
            }
            
            payload.put("sourceservice", "trade-capture");
            payload.put("status", status);


            String payloadJson = "{";
            boolean first = true;
            for (Map.Entry<String, String> entry : payload.entrySet()) {
                if (!first) payloadJson += ",";
                payloadJson += "\"" + entry.getKey() + "\":\"" + entry.getValue() + "\"";
                first = false;
            }
            payloadJson += "}";

            Map<String, String> streamData = new HashMap<>();
            streamData.put("payload", payloadJson);

            RecordId recordId = redisTemplate.opsForStream().add(
                StreamRecords.newRecord()
                    .in(streamKey)
                    .ofMap(streamData)
            );

            log.info("Sent status message to Redis stream: {} with recordId: {}", payloadJson, recordId.getValue());
            return recordId.getValue();
            
        } catch (Exception e) {
            log.error("Failed to send status message to Redis: {}", e.getMessage(), e);
            throw new RuntimeException("Failed to send status message", e);
        }
    }
}