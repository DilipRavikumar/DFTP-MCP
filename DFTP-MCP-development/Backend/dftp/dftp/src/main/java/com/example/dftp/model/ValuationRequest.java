package com.example.dftp.model;

import java.util.List;
import java.util.Map;

public class ValuationRequest {
    private List<String> tradeIds;
    private Map<String, Double> tradeAmounts; // optional per trade override
    private Double navFactor; // multiplier to simulate NAV effect
    private Double feePercent; // e.g. 0.005 for 0.5%

    public List<String> getTradeIds() { return tradeIds; }
    public void setTradeIds(List<String> tradeIds) { this.tradeIds = tradeIds; }
    public Map<String, Double> getTradeAmounts() { return tradeAmounts; }
    public void setTradeAmounts(Map<String, Double> tradeAmounts) { this.tradeAmounts = tradeAmounts; }
    public Double getNavFactor() { return navFactor; }
    public void setNavFactor(Double navFactor) { this.navFactor = navFactor; }
    public Double getFeePercent() { return feePercent; }
    public void setFeePercent(Double feePercent) { this.feePercent = feePercent; }
}
