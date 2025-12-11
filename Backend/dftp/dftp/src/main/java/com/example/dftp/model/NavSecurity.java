package com.example.dftp.model;


import java.math.BigDecimal;

public class NavSecurity {

    private String securityId;
    private BigDecimal nav;

    public NavSecurity() {}

    public NavSecurity(String securityId, BigDecimal nav) {
        this.securityId = securityId;
        this.nav = nav;
    }

    public String getSecurityId() { return securityId; }
    public void setSecurityId(String securityId) { this.securityId = securityId; }

    public BigDecimal getNav() { return nav; }
    public void setNav(BigDecimal nav) { this.nav = nav; }
}

