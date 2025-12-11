package com.dfpt.canonical.dto;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import com.opencsv.bean.CsvBindByName;
import java.math.BigDecimal;
@JacksonXmlRootElement(localName = "Order")
public class ExternalTradeDTO {
    @CsvBindByName(column = "originatorType")
    @JacksonXmlProperty(localName = "OriginatorType")
    private String originatorType;
    @CsvBindByName(column = "firmNumber")
    @JacksonXmlProperty(localName = "FirmNumber")
    private Integer firmNumber;
    @CsvBindByName(column = "fundNumber")
    @JacksonXmlProperty(localName = "FundNumber")
    private Integer fundNumber;
    @CsvBindByName(column = "transactionType")
    @JacksonXmlProperty(localName = "TransactionType")
    private String transactionType;
    @CsvBindByName(column = "transactionId")
    @JacksonXmlProperty(localName = "TransactionId")
    private String transactionId;
    @CsvBindByName(column = "tradeDateTime")
    @JacksonXmlProperty(localName = "TradeDateTime")
    private String tradeDateTime;
    @CsvBindByName(column = "dollarAmount")
    @JacksonXmlProperty(localName = "DollarAmount")
    private BigDecimal dollarAmount;
    @JacksonXmlProperty(localName = "ClientAccountNo")
    private Integer clientAccountNo;
    @CsvBindByName(column = "clientName")
    @JacksonXmlProperty(localName = "ClientName")
    private String clientName;
    @CsvBindByName(column = "ssn")
    @JacksonXmlProperty(localName = "SSN")
    private String ssn;
    @CsvBindByName(column = "dob")
    @JacksonXmlProperty(localName = "DOB")
    private String dob;
    @CsvBindByName(column = "shareQuantity")
    @JacksonXmlProperty(localName = "ShareQuantity")
    private BigDecimal shareQuantity;
    public String getOriginatorType() {
        return originatorType;
    }
    public void setOriginatorType(String originatorType) {
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
    public String getTradeDateTime() {
        return tradeDateTime;
    }
    public void setTradeDateTime(String tradeDateTime) {
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
    public String getDob() {
        return dob;
    }
    public void setDob(String dob) {
        this.dob = dob;
    }
    public BigDecimal getShareQuantity() {
        return shareQuantity;
    }
    public void setShareQuantity(BigDecimal shareQuantity) {
        this.shareQuantity = shareQuantity;
    }
}
