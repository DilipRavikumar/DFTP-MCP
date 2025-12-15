package com.dfpt.canonical.dto;
import java.math.BigDecimal;
public class FundDTO {
    private Integer fundId;
    private String schemeCode;
    private String status;
    private BigDecimal minLimit;
    private BigDecimal maxLimit;
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
    public BigDecimal getMinLimit() {
        return minLimit;
    }
    public void setMinLimit(BigDecimal minLimit) {
        this.minLimit = minLimit;
    }
    public BigDecimal getMaxLimit() {
        return maxLimit;
    }
    public void setMaxLimit(BigDecimal maxLimit) {
        this.maxLimit = maxLimit;
    }
}
