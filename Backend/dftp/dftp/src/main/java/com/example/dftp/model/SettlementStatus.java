package com.example.dftp.model;

import java.time.LocalDateTime;

public class SettlementStatus {
    private String tradeId;
    private String status; // RECEIVED, CONFIRMED, SETTLED
    private LocalDateTime updatedAt;

    public String getTradeId() { return tradeId; }
    public void setTradeId(String tradeId) { this.tradeId = tradeId; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
