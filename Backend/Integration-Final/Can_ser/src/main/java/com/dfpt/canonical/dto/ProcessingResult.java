package com.dfpt.canonical.dto;
import com.dfpt.canonical.model.CanonicalTrade;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
public class ProcessingResult {
    private String fileName;
    private String format;
    private LocalDateTime processedAt;
    private int totalRecords;
    private int successCount;
    private int failedCount;
    private List<CanonicalTrade> processedTrades;
    private List<String> errors;
    private String status; 
    public ProcessingResult() {
        this.processedTrades = new ArrayList<>();
        this.errors = new ArrayList<>();
        this.processedAt = LocalDateTime.now();
    }
    public String getFileName() {
        return fileName;
    }
    public void setFileName(String fileName) {
        this.fileName = fileName;
    }
    public String getFormat() {
        return format;
    }
    public void setFormat(String format) {
        this.format = format;
    }
    public LocalDateTime getProcessedAt() {
        return processedAt;
    }
    public void setProcessedAt(LocalDateTime processedAt) {
        this.processedAt = processedAt;
    }
    public int getTotalRecords() {
        return totalRecords;
    }
    public void setTotalRecords(int totalRecords) {
        this.totalRecords = totalRecords;
    }
    public int getSuccessCount() {
        return successCount;
    }
    public void setSuccessCount(int successCount) {
        this.successCount = successCount;
    }
    public int getFailedCount() {
        return failedCount;
    }
    public void setFailedCount(int failedCount) {
        this.failedCount = failedCount;
    }
    public List<CanonicalTrade> getProcessedTrades() {
        return processedTrades;
    }
    public void setProcessedTrades(List<CanonicalTrade> processedTrades) {
        this.processedTrades = processedTrades;
    }
    public List<String> getErrors() {
        return errors;
    }
    public void setErrors(List<String> errors) {
        this.errors = errors;
    }
    public String getStatus() {
        return status;
    }
    public void setStatus(String status) {
        this.status = status;
    }
    public void addError(String error) {
        this.errors.add(error);
    }
    public void addProcessedTrade(CanonicalTrade trade) {
        this.processedTrades.add(trade);
    }
    @Override
    public String toString() {
        return "ProcessingResult{" +
                "fileName='" + fileName + '\'' +
                ", format='" + format + '\'' +
                ", processedAt=" + processedAt +
                ", totalRecords=" + totalRecords +
                ", successCount=" + successCount +
                ", failedCount=" + failedCount +
                ", status='" + status + '\'' +
                ", errorsCount=" + errors.size() +
                '}';
    }
}
