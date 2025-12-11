package com.dfpt.canonical.service;

import com.dfpt.canonical.dto.StatusMessagePayload;
import com.dfpt.canonical.model.CanonicalTrade;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.connection.stream.RecordId;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class StatusStreamPublisher {
    
    private static final Logger logger = LoggerFactory.getLogger(StatusStreamPublisher.class);
    
    @Autowired
    private StringRedisTemplate redisTemplate;
    
    @Value("${redis.stream.name:status-stream}")
    private String streamName;
    
    private final ObjectMapper objectMapper = new ObjectMapper();
    

    public RecordId publishTradeStatus(CanonicalTrade trade) {
        try {

            StatusMessagePayload payload = new StatusMessagePayload();
            

            payload.setDistributorId(convertFirmToDistributor(trade.getFirmNumber()));
            

            if ("MQ".equalsIgnoreCase(trade.getOrderSource())) {

                payload.setOrderId(trade.getRawOrderId() != null ? trade.getRawOrderId().toString() : trade.getTransactionId());
                payload.setFileId("");
            } else if ("S3".equalsIgnoreCase(trade.getOrderSource())) {

                payload.setFileId(trade.getFileId() != null ? trade.getFileId().toString() : "");
                payload.setOrderId(trade.getRawOrderId() != null ? trade.getRawOrderId().toString() : trade.getTransactionId());
            } else {

                payload.setFileId(trade.getFileId() != null ? trade.getFileId().toString() : "");
                payload.setOrderId(trade.getRawOrderId() != null ? trade.getRawOrderId().toString() : trade.getTransactionId());
            }
            
            payload.setStatus(mapTradeStatus(trade.getStatus()));
            payload.setSourceservice("canonical");
            

            Map<String, String> streamData = new HashMap<>();
            streamData.put("payload", objectMapper.writeValueAsString(payload));
            streamData.put("timestamp", String.valueOf(System.currentTimeMillis()));
            

            RecordId recordId = redisTemplate.opsForStream().add(streamName, streamData);
            
            logger.info("✓ Published EDIS status: orderId={}, fileId={}, distributorId={}, status=VALIDATED, source={} - MessageId: {}", 
                payload.getOrderId(), payload.getFileId(), payload.getDistributorId(), trade.getOrderSource(), recordId);
            
            return recordId;
            
        } catch (Exception e) {
            logger.error("✗ Failed to publish EDIS status for trade: {}", trade.getTransactionId(), e);
            return null;
        }
    }
    

    public RecordId publishBatchStatus(String fileName, int totalRecords, 
                                       int successCount, int failedCount) {
        try {
            StatusMessagePayload payload = new StatusMessagePayload();
            payload.setDistributorId("BATCH");
            payload.setFileId(fileName);
            payload.setOrderId("BATCH-" + System.currentTimeMillis());
            payload.setStatus(failedCount == 0 ? "BATCH_SUCCESS" : "BATCH_PARTIAL");
            payload.setSourceservice("canonical");
            
            Map<String, String> streamData = new HashMap<>();
            streamData.put("payload", objectMapper.writeValueAsString(payload));
            streamData.put("timestamp", String.valueOf(System.currentTimeMillis()));
            streamData.put("totalRecords", String.valueOf(totalRecords));
            streamData.put("successCount", String.valueOf(successCount));
            streamData.put("failedCount", String.valueOf(failedCount));
            
            RecordId recordId = redisTemplate.opsForStream().add(streamName, streamData);
            
            logger.info("✓ Published batch EDIS status: {} - Success: {}/{} - MessageId: {}", 
                fileName, successCount, totalRecords, recordId);
            
            return recordId;
            
        } catch (Exception e) {
            logger.error("✗ Failed to publish batch EDIS status for: {}", fileName, e);
            return null;
        }
    }
    

    private String convertFirmToDistributor(Integer firmNumber) {
        if (firmNumber == null) {
            return "UNKNOWN";
        }
        return String.valueOf(firmNumber);
    }
    

    private String mapTradeStatus(String tradeStatus) {
        if (tradeStatus == null) return "UNKNOWN";
        switch (tradeStatus) {
            case "RECEIVED":
                return "RECEIVED";
            case "VALIDATED":
                return "VALIDATED";
            case "VALIDATION_FAILED":
                return "FAILED";
            case "FAILED":
                return "FAILED";
            default:
                return tradeStatus;
        }
    }
}
