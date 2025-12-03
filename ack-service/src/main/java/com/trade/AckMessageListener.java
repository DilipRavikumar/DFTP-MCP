package com.trade;

import org.springframework.jms.annotation.JmsListener;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Autowired;

@Component
public class AckMessageListener {
    
    @Autowired
    private AckLogRepository repository;
    
    @JmsListener(destination = "TRADE.FINAL")
    public void processFinalTrade(String message) {
        System.out.println("ACK Service received final trade: " + message);
        
        String[] parts = message.split(",");
        String tradeId = parts[0];
        String status = parts[1];
        
        // Save to database
        AckLog ackLog = new AckLog();
        ackLog.setTradeId(tradeId);
        ackLog.setStatus(status);
        ackLog.setDeliveryMethod("EMAIL");
        ackLog.setTimestamp(java.time.LocalDateTime.now());
        repository.save(ackLog);
        
        System.out.println("Sending " + status + " confirmation for trade: " + tradeId);
    }
}