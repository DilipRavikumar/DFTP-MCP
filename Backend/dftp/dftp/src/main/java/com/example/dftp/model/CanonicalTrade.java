package com.example.dftp.model;

import java.time.LocalDate;

public class CanonicalTrade {
    private String tradeId;
    private LocalDate tradeDate;
    private LocalDate settlementDate;
    private String assetType;
    private String assetId;
    private Double tradeAmount;
    private Double tradeVolume;
    private String currency;

    public String getTradeId() { return tradeId; }
    public void setTradeId(String tradeId) { this.tradeId = tradeId; }
    public LocalDate getTradeDate() { return tradeDate; }
    public void setTradeDate(LocalDate tradeDate) { this.tradeDate = tradeDate; }
    public LocalDate getSettlementDate() { return settlementDate; }
    public void setSettlementDate(LocalDate settlementDate) { this.settlementDate = settlementDate; }
    public String getAssetType() { return assetType; }
    public void setAssetType(String assetType) { this.assetType = assetType; }
    public String getAssetId() { return assetId; }
    public void setAssetId(String assetId) { this.assetId = assetId; }
    public Double getTradeAmount() { return tradeAmount; }
    public void setTradeAmount(Double tradeAmount) { this.tradeAmount = tradeAmount; }
    public Double getTradeVolume() { return tradeVolume; }
    public void setTradeVolume(Double tradeVolume) { this.tradeVolume = tradeVolume; }
    public String getCurrency() { return currency; }
    public void setCurrency(String currency) { this.currency = currency; }
}
