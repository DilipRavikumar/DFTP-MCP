package com.dfpt.canonical.model;

import jakarta.persistence.*;
import java.math.BigDecimal;

@Entity
@Table(name = "fund")
public class Fund {
    @Id
    @Column(name = "fund_id")
    private Integer fundId;
    @Column(name = "scheme_code", length = 50)
    private String schemeCode;
    @Column(name = "status", length = 20)
    private String status;  // ACTIVE, CLOSED, SUSPENDED
    @Column(name = "max_limit", precision = 18, scale = 2)
    private BigDecimal maxLimit;
    @Column(name = "min_limit", precision = 18, scale = 2)
    private BigDecimal minLimit;
    public Integer getFundId() {
        return fundId;
    }
    public void setFundId(Integer fundId) {
        this.fundId = fundId;
    }
    public String getSchemeCode() {
        return schemeCode;
    }
    public void setSchemeCode(String schemeCode) {
        this.schemeCode = schemeCode;
    }
    public String getStatus() {
        return status;
    }
    public void setStatus(String status) {
        this.status = status;
    }
    public BigDecimal getMaxLimit() {
        return maxLimit;
    }
    public void setMaxLimit(BigDecimal maxLimit) {
        this.maxLimit = maxLimit;
    }
    public BigDecimal getMinLimit() {
        return minLimit;
    }
    public void setMinLimit(BigDecimal minLimit) {
        this.minLimit = minLimit;
    }
}
