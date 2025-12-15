package com.example.dftp.model;


import java.math.BigDecimal;
import java.time.LocalDateTime;

public class OrderRequest {

    private String transactionId;
    private String clientName;
    private Integer fundNumber;
    private BigDecimal dollarAmount;
    private LocalDateTime receivedAt;

    public OrderRequest() {}

    public String getTransactionId() { return transactionId; }
    public void setTransactionId(String transactionId) { this.transactionId = transactionId; }

    public String getClientName() { return clientName; }
    public void setClientName(String clientName) { this.clientName = clientName; }

    public Integer getFundNumber() { return fundNumber; }
    public void setFundNumber(Integer fundNumber) { this.fundNumber = fundNumber; }

    public BigDecimal getDollarAmount() { return dollarAmount; }
    public void setDollarAmount(BigDecimal dollarAmount) { this.dollarAmount = dollarAmount; }

    public LocalDateTime getReceivedAt() { return receivedAt; }
    public void setReceivedAt(LocalDateTime receivedAt) { this.receivedAt = receivedAt; }
}

