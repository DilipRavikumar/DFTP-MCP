package com.dfpt.canonical.model;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.UUID;
@Entity
@Table(name = "canonical_trades", 
    indexes = {
        @Index(name = "idx_transaction_id", columnList = "transaction_id"),
        @Index(name = "idx_trade_datetime", columnList = "trade_datetime"),
        @Index(name = "idx_client_account", columnList = "client_account_no")
    },
    uniqueConstraints = {
        @UniqueConstraint(name = "uk_raw_order_transaction", columnNames = {"raw_order_id", "transaction_id"})
    }
)
public class CanonicalTrade {
    @Id
    @GeneratedValue(strategy = GenerationType.AUTO)
    private UUID id;
    @Column(name = "status")
    private String status;
    @Column(name = "created_at")
    private LocalDateTime createdAt;
    @Column(name = "originator_type")
    private Integer originatorType;
    @Column(name = "firm_number")
    private Integer firmNumber;
    @Column(name = "fund_number")
    private Integer fundNumber;
    @Column(name = "transaction_type")
    private String transactionType;
    @Column(name = "transaction_id")
    private String transactionId;
    
    @Column(name = "raw_order_id")
    private UUID rawOrderId;  // For MQ: from ingestion; For S3: UUID generated per trade
    
    @Column(name = "file_id")
    private UUID fileId;  // For MQ: null; For S3: raw_order_id from ingestion
    
    @Column(name = "order_source")
    private String orderSource;  // MQ or S3
    
    @Column(name = "trade_datetime")
    private LocalDateTime tradeDateTime;
    @Column(name = "dollar_amount")
    private BigDecimal dollarAmount;
    @Column(name = "client_account_no")
    private Integer clientAccountNo;
    @Column(name = "client_name")
    private String clientName;
    @Column(name = "ssn")
    private String ssn;
    @Column(name = "dob")
    private LocalDate dob;
    @Column(name = "share_quantity")
    private BigDecimal shareQuantity;
    @Column(name = "validation_errors", columnDefinition = "TEXT")
    private String validationErrors;  // JSON array of validation errors from Drools
    @Column(name = "validated_at")
    private LocalDateTime validatedAt;
    @Column(name = "request_id", length = 100)
    private String requestId;
    public UUID getId() {
        return id;
    }
    public void setId(UUID id) {
        this.id = id;
    }
    public String getStatus() {
        return status;
    }
    public void setStatus(String status) {
        this.status = status;
    }
    public LocalDateTime getCreatedAt() {
        return createdAt;
    }
    public void setCreatedAt(LocalDateTime createdAt) {
        this.createdAt = createdAt;
    }
    public Integer getOriginatorType() {
        return originatorType;
    }
    public void setOriginatorType(Integer originatorType) {
        this.originatorType = originatorType;
    }
    public Integer getFirmNumber() {
        return firmNumber;
    }
    public void setFirmNumber(Integer firmNumber) {
        this.firmNumber = firmNumber;
    }
    public Integer getFundNumber() {
        return fundNumber;
    }
    public void setFundNumber(Integer fundNumber) {
        this.fundNumber = fundNumber;
    }
    public String getTransactionType() {
        return transactionType;
    }
    public void setTransactionType(String transactionType) {
        this.transactionType = transactionType;
    }
    public String getTransactionId() {
        return transactionId;
    }
    public void setTransactionId(String transactionId) {
        this.transactionId = transactionId;
    }
    public LocalDateTime getTradeDateTime() {
        return tradeDateTime;
    }
    public void setTradeDateTime(LocalDateTime tradeDateTime) {
        this.tradeDateTime = tradeDateTime;
    }
    public BigDecimal getDollarAmount() {
        return dollarAmount;
    }
    public void setDollarAmount(BigDecimal dollarAmount) {
        this.dollarAmount = dollarAmount;
    }
    public Integer getClientAccountNo() {
        return clientAccountNo;
    }
    public void setClientAccountNo(Integer clientAccountNo) {
        this.clientAccountNo = clientAccountNo;
    }
    public String getClientName() {
        return clientName;
    }
    public void setClientName(String clientName) {
        this.clientName = clientName;
    }
    public String getSsn() {
        return ssn;
    }
    public void setSsn(String ssn) {
        this.ssn = ssn;
    }
    public LocalDate getDob() {
        return dob;
    }
    public void setDob(LocalDate dob) {
        this.dob = dob;
    }
    public BigDecimal getShareQuantity() {
        return shareQuantity;
    }
    public void setShareQuantity(BigDecimal shareQuantity) {
        this.shareQuantity = shareQuantity;
    }
    public String getValidationErrors() {
        return validationErrors;
    }
    public void setValidationErrors(String validationErrors) {
        this.validationErrors = validationErrors;
    }
    public LocalDateTime getValidatedAt() {
        return validatedAt;
    }
    public void setValidatedAt(LocalDateTime validatedAt) {
        this.validatedAt = validatedAt;
    }
    public String getRequestId() {
        return requestId;
    }
    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }
    
    public UUID getRawOrderId() {
        return rawOrderId;
    }
    
    public void setRawOrderId(UUID rawOrderId) {
        this.rawOrderId = rawOrderId;
    }
    
    public String getOrderSource() {
        return orderSource;
    }
    
    public void setOrderSource(String orderSource) {
        this.orderSource = orderSource;
    }
    
    public UUID getFileId() {
        return fileId;
    }
    
    public void setFileId(UUID fileId) {
        this.fileId = fileId;
    }
}
