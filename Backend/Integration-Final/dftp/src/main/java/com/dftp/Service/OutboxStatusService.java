package com.dftp.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.dftp.Entity.OutboxEventEntity;
import com.dftp.Repository.OutboxEventRepository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Service
@RequiredArgsConstructor
@Slf4j
public class OutboxStatusService {

    private final OutboxEventRepository outboxRepository;

    /**
     * Update outbox status to SENT when consumed by Central Event Publisher
     * PENDING → SENT
     */
    @Transactional
    public void updateStatusToSent(UUID outboxId) {
        try {
            Optional<OutboxEventEntity> eventOpt = outboxRepository.findById(outboxId);
            
            if (eventOpt.isEmpty()) {
                log.warn("⚠️ Outbox event not found: {}", outboxId);
                return;
            }
            
            OutboxEventEntity event = eventOpt.get();
            
            if (!"PENDING".equals(event.getStatus())) {
                log.warn("⚠️ Outbox {} is not PENDING (current status: {}), skipping SENT update", 
                        outboxId, event.getStatus());
                return;
            }
            
            event.setStatus("SENT");
            outboxRepository.save(event);
            
            log.info("✅ Outbox {} status updated: PENDING → SENT (consumed by Central Event Publisher)", outboxId);
            
        } catch (Exception e) {
            log.error("Failed to update outbox {} to SENT status", outboxId, e);
            throw e;
        }
    }

    /**
     * Update outbox status to SENT by raw order ID
     * Used when Central Event Publisher identifies by rawOrderId
     */
    @Transactional
    public void updateStatusToSentByRawOrderId(UUID rawOrderId) {
        try {
            List<OutboxEventEntity> events = outboxRepository.findByRawOrderId(rawOrderId);
            
            for (OutboxEventEntity event : events) {
                if ("PENDING".equals(event.getStatus())) {
                    event.setStatus("SENT");
                    outboxRepository.save(event);
                    log.info("✅ Outbox {} (rawOrderId={}) updated: PENDING → SENT", 
                            event.getId(), rawOrderId);
                }
            }
            
        } catch (Exception e) {
            log.error("Failed to update outbox status to SENT for rawOrderId {}", rawOrderId, e);
            throw e;
        }
    }
}
