package com.dfpt.canonical.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

public class StatusMessagePayload {
    
    @JsonProperty("distributorId")
    private String distributorId;
    
    @JsonProperty("fileId")
    private String fileId;
    

    
    @JsonProperty("orderId")
    private String orderId;
    
    @JsonProperty("status")
    private String status;
    
    @JsonProperty("sourceservice")
    private String sourceservice = "canonical-trade-service";

    public StatusMessagePayload() {}

    public StatusMessagePayload(String distributorId, String fileId, String orderId, String status, String sourceservice) {
        this.distributorId = distributorId;
        this.fileId = fileId;
        this.orderId = orderId;
        this.status = status;
        this.sourceservice = sourceservice;
    }

    public String getDistributorId() {
        return distributorId;
    }

    public void setDistributorId(String distributorId) {
        this.distributorId = distributorId;
    }

    public String getFileId() {
        return fileId;
    }

    public void setFileId(String fileId) {
        this.fileId = fileId;
    }



    public String getOrderId() {
        return orderId;
    }

    public void setOrderId(String orderId) {
        this.orderId = orderId;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public String getSourceservice() {
        return sourceservice;
    }

    public void setSourceservice(String sourceservice) {
        this.sourceservice = sourceservice;
    }
}
