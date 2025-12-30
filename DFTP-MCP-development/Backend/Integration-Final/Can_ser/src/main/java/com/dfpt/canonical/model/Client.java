package com.dfpt.canonical.model;

import jakarta.persistence.*;

@Entity
@Table(name = "client")
public class Client {
    @Id
    @Column(name = "client_id")
    private Integer clientId;
    @Column(name = "kyc_status", length = 20)
    private String kycStatus;  // VERIFIED, PENDING, FAILED
    @Column(name = "pan_number", length = 10)
    private String panNumber;
    @Column(name = "status", length = 20)
    private String status;  // ACTIVE, INACTIVE, SUSPENDED
    @Column(name = "type", length = 20)
    private String type;  // INDIVIDUAL, CORPORATE, NRI
    public Integer getClientId() {
        return clientId;
    }
    public void setClientId(Integer clientId) {
        this.clientId = clientId;
    }
    public String getKycStatus() {
        return kycStatus;
    }
    public void setKycStatus(String kycStatus) {
        this.kycStatus = kycStatus;
    }
    public String getPanNumber() {
        return panNumber;
    }
    public void setPanNumber(String panNumber) {
        this.panNumber = panNumber;
    }
    public String getStatus() {
        return status;
    }
    public void setStatus(String status) {
        this.status = status;
    }
    public String getType() {
        return type;
    }
    public void setType(String type) {
        this.type = type;
    }
}
