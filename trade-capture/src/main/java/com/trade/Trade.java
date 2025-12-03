package com.trade;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "trades")
public class Trade {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String name;
    private int quantity;
    private double price;
    private String status;
    private String ruleResult;
    private String fraudResult;
    private String ackResult;
    private LocalDateTime timestamp;
    
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public String getRuleResult() { return ruleResult; }
    public void setRuleResult(String ruleResult) { this.ruleResult = ruleResult; }
    
    public String getFraudResult() { return fraudResult; }
    public void setFraudResult(String fraudResult) { this.fraudResult = fraudResult; }
    
    public String getAckResult() { return ackResult; }
    public void setAckResult(String ackResult) { this.ackResult = ackResult; }
    
    public int getQuantity() { return quantity; }
    public void setQuantity(int quantity) { this.quantity = quantity; }
    
    public double getPrice() { return price; }
    public void setPrice(double price) { this.price = price; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public LocalDateTime getTimestamp() { return timestamp; }
    public void setTimestamp(LocalDateTime timestamp) { this.timestamp = timestamp; }
}