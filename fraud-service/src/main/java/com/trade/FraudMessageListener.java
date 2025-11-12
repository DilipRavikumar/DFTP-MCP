package com.trade;

import com.trade.FraudResult;
import com.trade.FraudResultRepository;
import org.springframework.jms.annotation.JmsListener;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class FraudMessageListener {

    @Autowired
    private JmsTemplate jmsTemplate;

    @Autowired
    private FraudResultRepository repository;

    @JmsListener(
            destination = "TRADE.RECEIVED.TOPIC",
            containerFactory = "jmsListenerContainerFactory",
            subscription = "FraudServiceSub" // Durable subscription
    )
    public void processTrade(String message) {
        System.out.println("===== FRAUD SERVICE LISTENER TRIGGERED =====");
        System.out.println("Fraud Service received: " + message);

        try {
            String[] parts = message.split(",");
            String tradeId = parts[0];
            String name = parts[1];
            int quantity = Integer.parseInt(parts[2]);
            double price = Double.parseDouble(parts[3]);

            System.out.println("Fraud Service - Parsed: TradeId=" + tradeId +
                    ", Name=" + name + ", Qty=" + quantity + ", Price=" + price);

            // Run fraud check logic (simplified here)
            String result = checkFraud(name, quantity, price);
            int riskScore = calculateRiskScore(quantity, price);
            String reason = getFraudReason(quantity, price);

            System.out.println("Fraud Service - CheckFraud result: " + result + ", RiskScore: " + riskScore);

            // Save to database
            FraudResult fraudResult = new FraudResult();
            fraudResult.setTradeId(tradeId);
            fraudResult.setResult(result);
            fraudResult.setRiskScore(riskScore);
            fraudResult.setReason(reason);
            fraudResult.setTimestamp(java.time.LocalDateTime.now());

            repository.save(fraudResult);
            System.out.println("Fraud Service - Saved result to DB for TradeId=" + tradeId);

            // Publish result to FRAUD.RESULT queue
            publishFraudResult(tradeId, result);

        } catch (Exception e) {
            System.out.println("===== FRAUD SERVICE ERROR =====");
            e.printStackTrace();
        }
        System.out.println("===== FRAUD SERVICE LISTENER COMPLETE =====");
    }

    private void publishFraudResult(String tradeId, String result) {
        try {
            // Ensure this is set to queue (not topic)
            jmsTemplate.setPubSubDomain(true); // FRAUD.RESULT is a queue
            jmsTemplate.convertAndSend("FRAUD.RESULT", tradeId + "," + result);
            System.out.println("Fraud Service - Published to FRAUD.RESULT queue: " + tradeId + "," + result);
        } catch (Exception e) {
            System.err.println("Error publishing FRAUD.RESULT message for TradeId=" + tradeId);
            e.printStackTrace();
        }
    }

    // --- Dummy logic for simulation ---
    private String checkFraud(String name, int quantity, double price) {
        if (quantity > 1000 || price > 100000) {
            return "REJECT";
        }
        return "APPROVE";
    }

    private int calculateRiskScore(int quantity, double price) {
        return (int) Math.min(100, (quantity * price) / 10000);
    }

    private String getFraudReason(int quantity, double price) {
        if (quantity > 1000) return "High quantity suspicious";
        if (price > 100000) return "High price suspicious";
        return "No fraud detected";
    }
}
