package com.dftp.Service;

import java.time.Instant;
import java.util.List;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.dftp.Entity.OutboxEventEntity;
import com.dftp.Repository.OutboxEventRepository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Service
@RequiredArgsConstructor
@Slf4j
public class OutboxProcessingScheduler {

    private final OutboxEventRepository outboxRepository;
    private final StatusTrackingService statusTrackingService;

    /**
     * Process NEW outbox events and send to Redis (Status-Tracking)
     * NEW → PENDING
     */
    @Scheduled(fixedDelay = 5000) // Run every 5 seconds
    @Transactional
    public void processNewEvents() {
        try {
            List<OutboxEventEntity> newEvents = outboxRepository.findByStatus("NEW");
            
            if (!newEvents.isEmpty()) {
                log.info("📤 Processing {} NEW outbox events", newEvents.size());
                
                for (OutboxEventEntity event : newEvents) {
                    try {
                        // Send to Redis (Status-Tracking)
                        String redisId = statusTrackingService.sendStatusMessage(
                            event.getRawOrderId(), 
                            event.getSource(), 
                            "received"
                        );
                        
                        if (redisId == null) {
                            throw new RuntimeException("Redis returned null ID");
                        }
                        
                        // Update to PENDING after successful Redis send
                        event.setStatus("PENDING");
                        event.setSentAt(Instant.now());
                        outboxRepository.save(event);
                        
                        log.info("✅ Outbox {} sent to Redis (Status-Tracking) → status=PENDING, redisId={}", 
                                event.getId(), redisId);
                        
                    } catch (Exception e) {
                        log.error("❌ Failed to send outbox {} to Redis: {}", event.getId(), e.getMessage());
                        // Keep status as NEW for retry in next cycle
                    }
                }
            }
        } catch (Exception e) {
            log.error("Error processing NEW outbox events", e);
        }
    }
}
