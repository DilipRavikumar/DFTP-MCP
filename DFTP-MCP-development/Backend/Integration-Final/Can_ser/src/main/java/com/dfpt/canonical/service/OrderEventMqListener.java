package com.dfpt.canonical.service;

import com.dfpt.canonical.dto.ValidationResult;
import com.dfpt.canonical.model.CanonicalTrade;
import com.dfpt.canonical.repository.CanonicalTradeRepository;

import jakarta.jms.Message;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jms.annotation.JmsListener;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;


@Component
public class OrderEventMqListener {
    
    private static final Logger logger = LoggerFactory.getLogger(OrderEventMqListener.class);
    
    @Autowired
    private FixedWidthParserService fixedWidthParserService;
    
    @Autowired
    private ValidationService validationService;
    
    @Autowired
    private CanonicalTradeRepository tradeRepository;
    
    @Autowired
    private StatusStreamPublisher statusPublisher;
    
    @Autowired
    private OutboxService outboxService;
    

    @JmsListener(destination = "${jms.queue.order-events:order.event}")
    public void receiveOrderEvent(String tradeLine, Message message) {
        logger.info("📥 Received order event from MQ - Length: {} chars", tradeLine.length());
        
        try {

            UUID rawOrderId = null;
            String source = null;
            try {
                String rawOrderIdStr = message.getStringProperty("rawOrderId");
                if (rawOrderIdStr != null && !rawOrderIdStr.isEmpty()) {
                    rawOrderId = UUID.fromString(rawOrderIdStr);
                    logger.info("📋 Raw Order ID: {}", rawOrderId);
                }
                source = message.getStringProperty("source");
                logger.info("📍 Source: {}", source);
            } catch (Exception e) {
                logger.warn("⚠️ Could not extract headers from message: {}", e.getMessage());
            }
            

            if (tradeLine == null || tradeLine.trim().length() < 130) {
                logger.warn("⚠️ Invalid trade line - too short: {}", tradeLine != null ? tradeLine.length() : 0);
                return;
            }
            
            CanonicalTrade canonical = fixedWidthParserService.parseLineToCanonical(tradeLine.trim());
            
            if (canonical == null) {
                logger.error("❌ Failed to parse trade line");
                return;
            }
            

            canonical.setRawOrderId(rawOrderId);
            canonical.setFileId(null);
            canonical.setOrderSource(source);
            
            logger.info("🔍 Validating trade: {} (rawOrderId: {}, fileId: null, source: {})", 
                canonical.getTransactionId(), rawOrderId, source);
            

            ValidationResult validationResult = validationService.validate(canonical);
            

            if (!validationResult.isValid() || !validationResult.getErrors().isEmpty()) {
                canonical.setStatus("VALIDATION_FAILED");
                canonical.setValidationErrors(String.join("; ", validationResult.getErrors()));
                logger.warn("⚠️ Trade validation failed: {} - Errors: {}", 
                    canonical.getTransactionId(), validationResult.getErrors());
            } else {
                canonical.setStatus("VALIDATED");
                logger.info("✅ Trade validated successfully: {}", canonical.getTransactionId());
            }
            
            canonical.setValidatedAt(LocalDateTime.now());
            

            CanonicalTrade saved = tradeRepository.save(canonical);
            logger.info("💾 Trade saved to DB: {} (rawOrderId: {})", saved.getTransactionId(), rawOrderId);
            

            try {
                statusPublisher.publishTradeStatus(saved);
                logger.info("📤 Published status to Redis Stream: {}", saved.getTransactionId());
            } catch (Exception statusEx) {
                logger.warn("⚠️ Failed to publish status for trade {}: {}", 
                    saved.getTransactionId(), statusEx.getMessage());
            }
            
            // Create outbox entry ONLY for successfully validated trades
            if ("VALIDATED".equals(saved.getStatus())) {
                try {
                    outboxService.createOutboxEntries(List.of(saved));
                    logger.info("📤 Created outbox entry for VALIDATED trade: {}", saved.getTransactionId());
                } catch (Exception outboxEx) {
                    logger.error("❌ Failed to create outbox entry for trade {}: {}", 
                        saved.getTransactionId(), outboxEx.getMessage());
                }
            } else {
                logger.info("⚠️ Skipping outbox entry for VALIDATION_FAILED trade: {}", saved.getTransactionId());
            }
            
        } catch (Exception e) {
            logger.error("❌ Error processing order event from MQ", e);

        }
    }
}
