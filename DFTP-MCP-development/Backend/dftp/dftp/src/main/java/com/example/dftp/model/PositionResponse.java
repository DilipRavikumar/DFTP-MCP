package com.example.dftp.model;


import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

public class PositionResponse {

    private UUID positionId;
    private Integer fundNumber;
    private String clientName;
    private LocalDate asOfDate;
    private BigDecimal totalValue;
    private BigDecimal shareQuantity;
    private List<Holding> holdings;

    public UUID getPositionId() { return positionId; }
    public void setPositionId(UUID positionId) { this.positionId = positionId; }

    public Integer getFundNumber() { return fundNumber; }
    public void setFundNumber(Integer fundNumber) { this.fundNumber = fundNumber; }

    public String getClientName() { return clientName; }
    public void setClientName(String clientName) { this.clientName = clientName; }

    public LocalDate getAsOfDate() { return asOfDate; }
    public void setAsOfDate(LocalDate asOfDate) { this.asOfDate = asOfDate; }

    public BigDecimal getTotalValue() { return totalValue; }
    public void setTotalValue(BigDecimal totalValue) { this.totalValue = totalValue; }

    public BigDecimal getShareQuantity() { return shareQuantity; }
    public void setShareQuantity(BigDecimal shareQuantity) { this.shareQuantity = shareQuantity; }

    public List<Holding> getHoldings() { return holdings; }
    public void setHoldings(List<Holding> holdings) { this.holdings = holdings; }
}

