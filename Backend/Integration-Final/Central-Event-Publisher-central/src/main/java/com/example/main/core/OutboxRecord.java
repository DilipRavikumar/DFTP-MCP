package com.example.main.core;
import java.util.UUID;
public class OutboxRecord {
    private UUID id;
    private String payload;
    private UUID rawOrderId;
    private String source;  // MQ or S3

    public OutboxRecord() {}

    public OutboxRecord(UUID id, String payload) {
        this.id = id;
        this.payload = payload;
    }

    public OutboxRecord(UUID id, String payload, UUID rawOrderId, String source) {
        this.id = id;
        this.payload = payload;
        this.rawOrderId = rawOrderId;
        this.source = source;
    }

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }
    public String getPayload() { return payload; }
    public void setPayload(String payload) { this.payload = payload; }
    public UUID getRawOrderId() { return rawOrderId; }
    public void setRawOrderId(UUID rawOrderId) { this.rawOrderId = rawOrderId; }
    public String getSource() { return source; }
    public void setSource(String source) { this.source = source; }
}
