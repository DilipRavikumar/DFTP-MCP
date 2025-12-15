package com.example.dftp.model;

import java.time.LocalDateTime;

public class SimulatorResult {
    private String messageId;
    private String s3Key;
    private LocalDateTime createdAt;

    public SimulatorResult() {}
    public SimulatorResult(String messageId, String s3Key, LocalDateTime createdAt) {
        this.messageId = messageId;
        this.s3Key = s3Key;
        this.createdAt = createdAt;
    }

    public String getMessageId() { return messageId; }
    public void setMessageId(String messageId) { this.messageId = messageId; }
    public String getS3Key() { return s3Key; }
    public void setS3Key(String s3Key) { this.s3Key = s3Key; }
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
