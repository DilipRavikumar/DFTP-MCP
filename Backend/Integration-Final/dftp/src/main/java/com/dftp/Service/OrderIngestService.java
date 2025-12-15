
package com.dftp.Service;

import java.security.MessageDigest;
import java.time.Instant;
import java.util.UUID;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.dftp.Entity.OutboxEventEntity;
import com.dftp.Entity.RawOrderEntity;
import com.dftp.Repository.OutboxEventRepository;
import com.dftp.Repository.RawOrderRepository;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Service
@RequiredArgsConstructor
@Slf4j
public class OrderIngestService {

    private final RawOrderRepository rawOrderRepository;
    private final OutboxEventRepository outboxRepository;
    private final SafeInboundQueue safeQueue;
    private final StatusTrackingService statusTrackingService;


    @Transactional
    public void ingestFromMq(String payload) {

        String checksum = generateChecksum(payload.getBytes());
        
        // Check for duplicates and skip processing if found
        if (isDuplicate(checksum)) {
            log.warn("Skipping duplicate message with checksum: {}", checksum);
            return;
        }

        RawOrderEntity raw = RawOrderEntity.builder()
                .id(UUID.randomUUID())
                .source("MQ")
                .payload(payload)              
                .checksum(checksum)
                .receivedAt(Instant.now())
                .build();

        rawOrderRepository.save(raw);
        createOutboxEvent(raw);
    }


    @Transactional
public void ingestFromSqs(String payload) {

    String checksum = generateChecksum(payload.getBytes());
    
    // Check for duplicates and skip processing if found
    if (isDuplicate(checksum)) {
        log.warn("Skipping duplicate S3 message with checksum: {}", checksum);
        return;
    }

    RawOrderEntity raw = RawOrderEntity.builder()
            .id(UUID.randomUUID())
            .source("S3")     
            .payload(payload)
            .checksum(checksum)
            .receivedAt(Instant.now())
            .build();

    rawOrderRepository.save(raw);
    createOutboxEvent(raw);
}

    
    private void createOutboxEvent(RawOrderEntity raw) {

        OutboxEventEntity evt = OutboxEventEntity.builder()
                .id(UUID.randomUUID())
                .rawOrderId(raw.getId())
                .source(raw.getSource())
                .eventType("OrderReceivedEvent")
                .payload(raw.getPayload())   
                .status("NEW")  // Start as NEW, scheduler will send to Redis
                .createdAt(Instant.now())
                .build();

        outboxRepository.save(evt);
        log.info("✅ Created outbox entry with status=NEW for rawOrderId: {}", raw.getId());
    }


    private boolean isDuplicate(String checksum) {
        return rawOrderRepository.findByChecksum(checksum).isPresent();
    }


    private String generateChecksum(byte[] bytes) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(bytes);
            StringBuilder hex = new StringBuilder();
            for (byte b : hash) hex.append(String.format("%02x", b));
            return hex.toString();
        } catch (Exception e) {
            throw new RuntimeException("Checksum generation failed", e);
        }
    }


    private String detectFileType(String filename) {
        if (filename == null) return "UNKNOWN";
        String f = filename.toLowerCase();
        if (f.endsWith(".csv")) return "CSV_FILE";
        if (f.endsWith(".json")) return "JSON_FILE";
        if (f.endsWith(".xml")) return "XML_FILE";
        return "FILE";
    }


    @Transactional
    public void processInboundMessages() {
        String msg;
        while ((msg = safeQueue.poll()) != null) {
            ingestFromMq(msg);
        }
    }
}


