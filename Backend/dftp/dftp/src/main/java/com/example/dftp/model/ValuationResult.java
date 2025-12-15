package com.example.dftp.model;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public class ValuationResult {
    private String valuationId;
    private String tradeId;
    private BigDecimal grossAmount;
    private BigDecimal fees;
    private BigDecimal netAmount;
    private LocalDateTime calculatedAt;

    public String getValuationId() { return valuationId; }
    public void setValuationId(String valuationId) { this.valuationId = valuationId; }
    public String getTradeId() { return tradeId; }
    public void setTradeId(String tradeId) { this.tradeId = tradeId; }
    public BigDecimal getGrossAmount() { return grossAmount; }
    public void setGrossAmount(BigDecimal grossAmount) { this.grossAmount = grossAmount; }
    public BigDecimal getFees() { return fees; }
    public void setFees(BigDecimal fees) { this.fees = fees; }
    public BigDecimal getNetAmount() { return netAmount; }
    public void setNetAmount(BigDecimal netAmount) { this.netAmount = netAmount; }
    public LocalDateTime getCalculatedAt() { return calculatedAt; }
    public void setCalculatedAt(LocalDateTime calculatedAt) { this.calculatedAt = calculatedAt; }
}
