package com.example.dftp.model;

import java.time.LocalDate;
import java.util.List;

public class NavResponse {

    private Integer fundNumber;
    private LocalDate asOfDate;
    private String fileName;
    private Integer totalSecurities;
    private List<NavSecurity> securities;

    public Integer getFundNumber() { return fundNumber; }
    public void setFundNumber(Integer fundNumber) { this.fundNumber = fundNumber; }

    public LocalDate getAsOfDate() { return asOfDate; }
    public void setAsOfDate(LocalDate asOfDate) { this.asOfDate = asOfDate; }

    public String getFileName() { return fileName; }
    public void setFileName(String fileName) { this.fileName = fileName; }

    public Integer getTotalSecurities() { return totalSecurities; }
    public void setTotalSecurities(Integer totalSecurities) { this.totalSecurities = totalSecurities; }

    public List<NavSecurity> getSecurities() { return securities; }
    public void setSecurities(List<NavSecurity> securities) { this.securities = securities; }
}

