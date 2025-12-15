package com.dfpt.canonical.service;

import com.dfpt.canonical.model.CanonicalTrade;
import com.dfpt.canonical.model.OutboxEntity;
import com.dfpt.canonical.model.OutboxStatus;
import com.dfpt.canonical.repository.OutboxRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.connection.stream.RecordId;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.StreamOperations;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class OutboxService {

    private static final Logger logger = LoggerFactory.getLogger(OutboxService.class);
    private static final int MAX_RETRY_ATTEMPTS = 3;
    private static final String REDIS_STREAM_KEY = "trade-events-stream";

    @Autowired
    private OutboxRepository outboxRepository;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private RedisTemplate<String, Object> redisTemplate;

    /**
     * Batch processed entries saved to outbox
     */
    @Transactional
    public void createOutboxEntries(List<CanonicalTrade> savedTrades) {
        logger.info("🎯 OutboxService.createOutboxEntries() called with {} trades", savedTrades != null ? savedTrades.size() : 0);
        
        if (savedTrades == null || savedTrades.isEmpty()) {
            logger.warn("⚠️ No trades provided to createOutboxEntries");
            return;
        }
        
        List<OutboxEntity> outboxList = new ArrayList<>();

        for (CanonicalTrade saved : savedTrades) {
            try {
                String payloadJson = objectMapper.writeValueAsString(saved);

                OutboxEntity outbox = new OutboxEntity();
                
                // Use the ingestion ID: rawOrderId for MQ, fileId for S3
                UUID aggregateId;
                if ("MQ".equalsIgnoreCase(saved.getOrderSource())) {
                    // For MQ orders: use rawOrderId
                    aggregateId = saved.getRawOrderId() != null ? saved.getRawOrderId() : saved.getId();
                    logger.debug("MQ order - using rawOrderId: {}", aggregateId);
                } else if ("S3".equalsIgnoreCase(saved.getOrderSource())) {
                    // For S3 files: use fileId (batch identifier)
                    aggregateId = saved.getFileId() != null ? saved.getFileId() : saved.getId();
                    logger.debug("S3 order - using fileId: {}", aggregateId);
                } else {
                    // Fallback: use canonical trade ID
                    aggregateId = saved.getId();
                    logger.debug("Unknown source - using canonical ID: {}", aggregateId);
                }
                
                outbox.setAggregateId(aggregateId);
                outbox.setPayload(payloadJson);
                outbox.setStatus(OutboxStatus.NEW.name());
                outbox.setTradeDateTime(saved.getTradeDateTime());  
                outbox.setCreatedAt(LocalDateTime.now());
                outbox.setRetryCount(0);

                outboxList.add(outbox);

            } catch (Exception e) {
                logger.error("JSON conversion failed for trade ID: {}", saved.getId(), e);
                throw new RuntimeException("JSON conversion failed", e);
            }
        }

        logger.info("💾 About to save {} outbox entries to database", outboxList.size());
        outboxRepository.saveAll(outboxList);
        logger.info("✅ Successfully created {} outbox entries in database", outboxList.size());
    }

    /**
     * Process NEW events and send them to Redis Stream
     */
    @Scheduled(fixedDelay = 5000) // Run every 5 seconds
    @Transactional
    public void processNewEvents() {
        try {
            List<OutboxEntity> newEvents = outboxRepository.findNewEvents();
            
            if (!newEvents.isEmpty()) {
                logger.info("Processing {} new outbox events", newEvents.size());
                
                for (OutboxEntity event : newEvents) {
                    try {
                        RecordId recordId = sendToRedisStream(event);

                        // On successful publish, capture Redis id (ACK) and mark PENDING
                        event.setRedisMessageId(recordId != null ? recordId.getValue() : null);
                        event.setAckReceivedAt(LocalDateTime.now());
                        event.setStatus(OutboxStatus.PENDING.name());
                        event.setLastAttemptAt(LocalDateTime.now());
                        outboxRepository.save(event);
                        
                        logger.debug("Successfully sent event {} to Redis stream with id {}", event.getOutboxId(), recordId);
                        
                    } catch (Exception e) {
                        logger.error("Failed to send event {} to Redis stream", event.getOutboxId(), e);
                        
                        // Mark as FAILED and increment retry count
                        event.setStatus(OutboxStatus.FAILED.name());
                        event.setRetryCount(event.getRetryCount() + 1);
                        event.setLastAttemptAt(LocalDateTime.now());
                        outboxRepository.save(event);
                    }
                }
            }
        } catch (Exception e) {
            logger.error("Error processing new outbox events", e);
        }
    }

    /**
     * Retry failed events
     */
    @Scheduled(fixedDelay = 30000) // Run every 30 seconds
    @Transactional
    public void retryFailedEvents() {
        try {
            List<OutboxEntity> retryableEvents = outboxRepository.findRetryableEvents(MAX_RETRY_ATTEMPTS);
            
            if (!retryableEvents.isEmpty()) {
                logger.info("Retrying {} failed outbox events", retryableEvents.size());
                
                for (OutboxEntity event : retryableEvents) {
                    try {
                        RecordId recordId = sendToRedisStream(event);

                        // Update status to PENDING and capture Redis id
                        event.setRedisMessageId(recordId != null ? recordId.getValue() : null);
                        event.setAckReceivedAt(LocalDateTime.now());
                        event.setStatus(OutboxStatus.PENDING.name());
                        event.setLastAttemptAt(LocalDateTime.now());
                        outboxRepository.save(event);
                        
                        logger.info("Successfully retried event {} after {} attempts, redisId={}", 
                                   event.getOutboxId(), event.getRetryCount(), recordId);
                        
                    } catch (Exception e) {
                        logger.error("Retry failed for event {} (attempt {})", 
                                   event.getOutboxId(), event.getRetryCount() + 1, e);
                        
                        // Increment retry count
                        event.setRetryCount(event.getRetryCount() + 1);
                        event.setLastAttemptAt(LocalDateTime.now());
                        
                        // If max retries exceeded, keep as FAILED
                        if (event.getRetryCount() >= MAX_RETRY_ATTEMPTS) {
                            logger.error("Max retry attempts exceeded for event {}", event.getOutboxId());
                        }
                        
                        outboxRepository.save(event);
                    }
                }
            }
        } catch (Exception e) {
            logger.error("Error retrying failed outbox events", e);
        }
    }

    /**
     * Send event to Redis Stream
     */
    private RecordId sendToRedisStream(OutboxEntity event) {
        try {
            StreamOperations<String, Object, Object> streamOps = redisTemplate.opsForStream();
            
            Map<String, Object> eventData = new HashMap<>();
            eventData.put("aggregateId", event.getAggregateId().toString());
            eventData.put("payload", event.getPayload());
            eventData.put("tradeDateTime", event.getTradeDateTime().toString());
            eventData.put("outboxId", event.getOutboxId().toString());
            
            RecordId recordId = streamOps.add(REDIS_STREAM_KEY, eventData);
            
            logger.debug("Event {} sent to Redis stream {} with id {}", event.getOutboxId(), REDIS_STREAM_KEY, recordId);
            return recordId;
        } catch (Exception e) {
            logger.error("Failed to send event {} to Redis stream", event.getOutboxId(), e);
            throw e; // Re-throw to trigger retry logic
        }
    }

    /**
     * Clean up old completed events (optional)
     */
    @Scheduled(fixedDelay = 3600000) // Run every hour
    @Transactional
    public void cleanupOldEvents() {
        try {
            LocalDateTime cutoffTime = LocalDateTime.now().minusDays(7); // Keep for 7 days
            List<OutboxEntity> oldEvents = outboxRepository.findCompletedEventsOlderThan(cutoffTime);
            
            if (!oldEvents.isEmpty()) {
                outboxRepository.deleteAll(oldEvents);
                logger.info("Cleaned up {} old outbox events", oldEvents.size());
            }
        } catch (Exception e) {
            logger.error("Error during outbox cleanup", e);
        }
    }

    /**
     * Update outbox status to SENT when consumed by Central Event Publisher
     */
    @Transactional
    public void updateStatusToSent(UUID outboxId) {
        try {
            OutboxEntity event = outboxRepository.findById(outboxId)
                .orElseThrow(() -> new RuntimeException("Outbox event not found: " + outboxId));
            
            event.setStatus(OutboxStatus.SENT.name());
            event.setLastAttemptAt(LocalDateTime.now());
            outboxRepository.save(event);
            
            logger.info("✅ Outbox {} status updated to SENT (consumed by Central Event Publisher)", outboxId);
        } catch (Exception e) {
            logger.error("Failed to update outbox {} to SENT status", outboxId, e);
            throw e;
        }
    }

    /**
     * Update outbox status to SENT by aggregate ID (for Central Event Publisher)
     */
    @Transactional
    public void updateStatusToSentByAggregateId(UUID aggregateId) {
        try {
            List<OutboxEntity> events = outboxRepository.findByAggregateId(aggregateId);
            
            for (OutboxEntity event : events) {
                if (OutboxStatus.PENDING.name().equals(event.getStatus())) {
                    event.setStatus(OutboxStatus.SENT.name());
                    event.setLastAttemptAt(LocalDateTime.now());
                    outboxRepository.save(event);
                    logger.info("✅ Outbox {} (aggregateId={}) status updated to SENT", event.getOutboxId(), aggregateId);
                }
            }
        } catch (Exception e) {
            logger.error("Failed to update outbox status to SENT for aggregateId {}", aggregateId, e);
            throw e;
        }
    }

    /**
     * Get outbox statistics
     */
    public Map<String, Long> getOutboxStatistics() {
        Map<String, Long> stats = new HashMap<>();
        
        try {
            stats.put("NEW", (long) outboxRepository.findByStatus("NEW").size());
            stats.put("PENDING", (long) outboxRepository.findByStatus("PENDING").size());
            stats.put("SENT", (long) outboxRepository.findByStatus("SENT").size());
            stats.put("FAILED", (long) outboxRepository.findByStatus("FAILED").size());
        } catch (Exception e) {
            logger.error("Error retrieving outbox statistics", e);
        }
        
        return stats;
    }
}