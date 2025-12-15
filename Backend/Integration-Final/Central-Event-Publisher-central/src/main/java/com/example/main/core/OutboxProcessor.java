package com.example.main.core;


import org.slf4j.Logger;
import java.util.UUID;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.lang.Nullable;

import com.example.main.config.OutboxProperties;
@Component
public class OutboxProcessor {

    private static final Logger log = LoggerFactory.getLogger(OutboxProcessor.class);

    private final GenericOutboxRepository jdbcRepository;
    private final MongoOutboxRepository mongoRepository;
    private final OutboxMessagePublisher publisher;
    private final OutboxProperties props;

    public OutboxProcessor(GenericOutboxRepository jdbcRepository,
                           @Nullable MongoOutboxRepository mongoRepository,
                           OutboxMessagePublisher publisher,
                           OutboxProperties props) {
        this.jdbcRepository = jdbcRepository;
        this.mongoRepository = mongoRepository;
        this.publisher = publisher;
        this.props = props;
    }

    @Scheduled(fixedDelayString = "${outbox.polling-interval-ms:3000}")
    public void processOnce() {
        try {
            OutboxRecord rec = null;
            

            if (props.getDatabaseType() == OutboxProperties.DatabaseType.MONGODB && mongoRepository != null) {
                rec = mongoRepository.fetchNextPending(props.getPendingStatus());
            } else if (jdbcRepository != null) {
                rec = jdbcRepository.fetchNextPending(props.getPendingStatus());
            }
            
            if (rec == null) return;

            log.info("Got outbox id={} rawOrderId={} source={} payload={}", rec.getId(), rec.getRawOrderId(), rec.getSource(), rec.getPayload());
            publisher.publish(rec.getPayload(), rec.getRawOrderId(), rec.getSource());
            

            if (props.getDatabaseType() == OutboxProperties.DatabaseType.MONGODB && mongoRepository != null) {
                mongoRepository.updateStatus(rec.getId(), props.getSentStatus());
            } else if (jdbcRepository != null) {
                jdbcRepository.updateStatus(rec.getId(), props.getSentStatus());
            }
            
            log.info("Marked outbox id={} as {}", rec.getId(), props.getSentStatus());
        } catch (Exception e) {
            log.error("Outbox processing error", e);

        }
    }
}
