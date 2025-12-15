package com.example.dftp.model;

public class ExceptionDTO {
    private String exceptionId;
    private String sourceService;
    private String sourceId; // tradeId or navId
    private String errorCode;
    private String errorMessage;
    private String severity; // LOW/MEDIUM/HIGH/CRITICAL
    private Double amountImpact;
    private String status; // OPEN/ACK/RESOLVED

    public ExceptionDTO() {}
    public ExceptionDTO(String exceptionId, String sourceService, String sourceId, String errorCode, String errorMessage, String severity, Double amountImpact, String status) {
        this.exceptionId = exceptionId; this.sourceService = sourceService; this.sourceId = sourceId;
        this.errorCode = errorCode; this.errorMessage = errorMessage; this.severity = severity; this.amountImpact = amountImpact; this.status = status;
    }

    public String getExceptionId() { return exceptionId; }
    public void setExceptionId(String exceptionId) { this.exceptionId = exceptionId; }
    public String getSourceService() { return sourceService; }
    public void setSourceService(String sourceService) { this.sourceService = sourceService; }
    public String getSourceId() { return sourceId; }
    public void setSourceId(String sourceId) { this.sourceId = sourceId; }
    public String getErrorCode() { return errorCode; }
    public void setErrorCode(String errorCode) { this.errorCode = errorCode; }
    public String getErrorMessage() { return errorMessage; }
    public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
    public String getSeverity() { return severity; }
    public void setSeverity(String severity) { this.severity = severity; }
    public Double getAmountImpact() { return amountImpact; }
    public void setAmountImpact(Double amountImpact) { this.amountImpact = amountImpact; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
