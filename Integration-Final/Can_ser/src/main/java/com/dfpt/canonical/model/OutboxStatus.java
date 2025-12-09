package com.dfpt.canonical.model;

public enum OutboxStatus {
    NEW,        // Event created but not yet sent to Redis (Status-Tracking)
    PENDING,    // Event sent to Redis (Status-Tracking), waiting for consumption by Central Event Publisher
    SENT,       // Event polled/consumed by Central Event Publisher
    COMPLETED,  // Event successfully processed by Event-pub sub
    FAILED      // Event processing failed (after max retries)
}