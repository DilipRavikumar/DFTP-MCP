package com.example.main.core;

import java.util.UUID;

public interface OutboxMessagePublisher {
    /**
     * Publish payload to MQ. Throw exception on failure.
     */
    void publish(String payload, UUID rawOrderId, String source) throws Exception;
}
