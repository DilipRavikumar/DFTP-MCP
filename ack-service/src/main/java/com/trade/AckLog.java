package com.trade;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "ack_logs")
public class AckLog {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    private String tradeId;
    private String status;
    private String deliveryMethod;
    private LocalDateTime timestamp;
    
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getTradeId() { return tradeId; }
    public void setTradeId(String tradeId) { this.tradeId = tradeId; }
    
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    
    public String getDeliveryMethod() { return deliveryMethod; }
    public void setDeliveryMethod(String deliveryMethod) { this.deliveryMethod = deliveryMethod; }
    
    public LocalDateTime getTimestamp() { return timestamp; }
    public void setTimestamp(LocalDateTime timestamp) { this.timestamp = timestamp; }
}