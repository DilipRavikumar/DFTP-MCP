package com.trade;

import org.springframework.jms.annotation.JmsListener;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class RuleMessageListener {

    @Autowired
    private JmsTemplate jmsTemplate;

    @Autowired
    private RuleResultRepository repository;

    @JmsListener(
            destination = "TRADE.RECEIVED.TOPIC",
            containerFactory = "jmsListenerContainerFactory",  // important for topics
            subscription = "RuleServiceSub"             // durable subscription name
    )
    public void processTrade(String message) {
        System.out.println("===== RULE SERVICE LISTENER TRIGGERED =====");
        System.out.println("Rule Service received: " + message);

        try {
            String[] parts = message.split(",");
            String tradeId = parts[0];
            String name = parts[1];
            int quantity = Integer.parseInt(parts[2]);
            double price = Double.parseDouble(parts[3]);

            System.out.println("Rule Service - Parsed: TradeId=" + tradeId + ", Name=" + name + ", Qty=" + quantity + ", Price=" + price);

            String result = validateTrade(name, quantity, price);
            String reason = getReason(name, quantity, price);

            System.out.println("Rule Service - ValidateTrade result: " + result);

            // Save to database
            RuleResult ruleResult = new RuleResult();
            ruleResult.setTradeId(tradeId);
            ruleResult.setResult(result);
            ruleResult.setReason(reason);
            ruleResult.setTimestamp(java.time.LocalDateTime.now());
            repository.save(ruleResult);
            System.out.println("Rule Service - Saved to database: " + tradeId);

            // Send to result queue (can be a queue or topic)
            jmsTemplate.setPubSubDomain(true); // queue mode for results
            jmsTemplate.convertAndSend("RULE.RESULT", tradeId + "," + result);
            System.out.println("Rule Service - Published to RULE.RESULT: " + tradeId + "," + result);
        } catch (Exception e) {
            System.out.println("===== RULE SERVICE ERROR =====");
            e.printStackTrace();
        }
        System.out.println("===== RULE SERVICE LISTENER COMPLETE =====");
    }

    private String validateTrade(String name, int quantity, double price) {
        if (quantity <= 0) return "REJECT";
        if (price <= 0) return "REJECT";
        if (name == null || name.length() < 2) return "REJECT";
        return "APPROVE";
    }

    private String getReason(String name, int quantity, double price) {
        if (quantity <= 0) return "Invalid quantity";
        if (price <= 0) return "Invalid price";
        if (name == null || name.length() < 2) return "Invalid name";
        return "Passed all rules";
    }
}
