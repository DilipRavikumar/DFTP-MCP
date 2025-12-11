package com.example.dftp.model;


import java.math.BigDecimal;

public class Holding {

    private String securityId;
    private BigDecimal value;
    private int allocationPercent;

    public Holding() {}

    public Holding(String securityId, BigDecimal value, int allocationPercent) {
        this.securityId = securityId;
        this.value = value;
        this.allocationPercent = allocationPercent;
    }

    public String getSecurityId() { return securityId; }
    public void setSecurityId(String securityId) { this.securityId = securityId; }

    public BigDecimal getValue() { return value; }
    public void setValue(BigDecimal value) { this.value = value; }

    public int getAllocationPercent() { return allocationPercent; }
    public void setAllocationPercent(int allocationPercent) { this.allocationPercent = allocationPercent; }
}

