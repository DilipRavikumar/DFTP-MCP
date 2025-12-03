package com.trade;

import org.springframework.jms.annotation.JmsListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class TradeMessageListener {
    
    @Autowired
    private TradeService tradeService;
    
    @JmsListener(destination = "RULE.RESULT", containerFactory = "jmsListenerContainerFactory")
    public void handleRuleResult(String message) {
        System.out.println("Received rule result: " + message);
        tradeService.processRuleResult(message);
    }
    
    @JmsListener(destination = "FRAUD.RESULT", containerFactory = "jmsListenerContainerFactory")
    public void handleFraudResult(String message) {
        System.out.println("Received fraud result: " + message);
        tradeService.processFraudResult(message);
    }
}