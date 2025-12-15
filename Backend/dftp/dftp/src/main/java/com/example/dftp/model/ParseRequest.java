package com.example.dftp.model;

import java.time.LocalDate;

public class ParseRequest {
    private String referenceId; // raw message id or s3 key
    private String formatHint;  // e.g. "CSV", "FIX", "BAD-FORMAT"
    private LocalDate tradeDate;
    private LocalDate settlementDate;
    private Double tradeAmount;
    private Double tradeVolume;
    private Double defaultAmount = 10000.0;


    public String getReferenceId() { return referenceId; }
    public void setReferenceId(String referenceId) { this.referenceId = referenceId; }
    public String getFormatHint() { return formatHint; }
    public void setFormatHint(String formatHint) { this.formatHint = formatHint; }
    public LocalDate getTradeDate() { return tradeDate; }
    public void setTradeDate(LocalDate tradeDate) { this.tradeDate = tradeDate; }
    public LocalDate getSettlementDate() { return settlementDate; }
    public void setSettlementDate(LocalDate settlementDate) { this.settlementDate = settlementDate; }
    public Double getTradeAmount() { return tradeAmount; }
    public void setTradeAmount(Double tradeAmount) { this.tradeAmount = tradeAmount; }
    public Double getTradeVolume() { return tradeVolume; }
    public void setTradeVolume(Double tradeVolume) { this.tradeVolume = tradeVolume; }
    public Double getDefaultAmount() { return defaultAmount; }
    public void setDefaultAmount(Double defaultAmount) { this.defaultAmount = defaultAmount; }
}
