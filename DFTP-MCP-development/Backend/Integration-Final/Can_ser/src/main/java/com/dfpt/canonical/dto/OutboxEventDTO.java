package com.dfpt.canonical.dto;

import java.time.LocalDateTime;
import java.util.UUID;

public class OutboxEventDTO {
    
    private UUID eventId;
    private UUID aggregateId;
    private String aggregateType;
    private String eventType;
    private Object eventData;  // Will be serialized to JSON
    private String streamName;
    private LocalDateTime timestamp;
    private String correlationId;
    private String source;
    
    // Constructors
    public OutboxEventDTO() {
        this.timestamp = LocalDateTime.now();
        this.eventId = UUID.randomUUID();
    }
    
    public OutboxEventDTO(UUID aggregateId, String aggregateType, String eventType, 
                         Object eventData, String streamName) {
        this();
        this.aggregateId = aggregateId;
        this.aggregateType = aggregateType;
        this.eventType = eventType;
        this.eventData = eventData;
        this.streamName = streamName;
        this.source = "can-ser";
    }
    
    // Builder pattern for easy creation
    public static Builder builder() {
        return new Builder();
    }
    
    public static class Builder {
        private final OutboxEventDTO dto = new OutboxEventDTO();
        
        public Builder aggregateId(UUID aggregateId) {
            dto.aggregateId = aggregateId;
            return this;
        }
        
        public Builder aggregateType(String aggregateType) {
            dto.aggregateType = aggregateType;
            return this;
        }
        
        public Builder eventType(String eventType) {
            dto.eventType = eventType;
            return this;
        }
        
        public Builder eventData(Object eventData) {
            dto.eventData = eventData;
            return this;
        }
        
        public Builder streamName(String streamName) {
            dto.streamName = streamName;
            return this;
        }
        
        public Builder correlationId(String correlationId) {
            dto.correlationId = correlationId;
            return this;
        }
        
        public Builder source(String source) {
            dto.source = source;
            return this;
        }
        
        public OutboxEventDTO build() {
            return dto;
        }
    }
    
    // Getters and Setters
    public UUID getEventId() {
        return eventId;
    }
    
    public void setEventId(UUID eventId) {
        this.eventId = eventId;
    }
    
    public UUID getAggregateId() {
        return aggregateId;
    }
    
    public void setAggregateId(UUID aggregateId) {
        this.aggregateId = aggregateId;
    }
    
    public String getAggregateType() {
        return aggregateType;
    }
    
    public void setAggregateType(String aggregateType) {
        this.aggregateType = aggregateType;
    }
    
    public String getEventType() {
        return eventType;
    }
    
    public void setEventType(String eventType) {
        this.eventType = eventType;
    }
    
    public Object getEventData() {
        return eventData;
    }
    
    public void setEventData(Object eventData) {
        this.eventData = eventData;
    }
    
    public String getStreamName() {
        return streamName;
    }
    
    public void setStreamName(String streamName) {
        this.streamName = streamName;
    }
    
    public LocalDateTime getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }
    
    public String getCorrelationId() {
        return correlationId;
    }
    
    public void setCorrelationId(String correlationId) {
        this.correlationId = correlationId;
    }
    
    public String getSource() {
        return source;
    }
    
    public void setSource(String source) {
        this.source = source;
    }
    
    @Override
    public String toString() {
        return "OutboxEventDTO{" +
                "eventId=" + eventId +
                ", aggregateId=" + aggregateId +
                ", aggregateType='" + aggregateType + '\'' +
                ", eventType='" + eventType + '\'' +
                ", streamName='" + streamName + '\'' +
                ", timestamp=" + timestamp +
                ", source='" + source + '\'' +
                '}';
    }
}