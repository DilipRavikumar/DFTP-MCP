package com.trade;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Trade submission response")
public class TradeResponse {
    
    @Schema(description = "Processing status", example = "RECEIVED")
    private String status;
    
    @Schema(description = "Trade ID", example = "12345")
    private String tradeId;
    
    public TradeResponse(String status, String tradeId) {
        this.status = status;
        this.tradeId = tradeId;
    }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public String getTradeId() { return tradeId; }
    public void setTradeId(String tradeId) { this.tradeId = tradeId; }
}