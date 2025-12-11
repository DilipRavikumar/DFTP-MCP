package com.example.main.publisher;

import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.stereotype.Component;

import com.example.main.core.OutboxMessagePublisher;

@Component
public class ActiveMqOutboxPublisher implements OutboxMessagePublisher {

    private final JmsTemplate jmsTemplate;
    private final String queueName;

    public ActiveMqOutboxPublisher(JmsTemplate jmsTemplate,
                                   @Value("${outbox.queue-name}") String queueName) {
        this.jmsTemplate = jmsTemplate;
        this.queueName = queueName;
    }

    @Override
    public void publish(String payload, UUID rawOrderId, String source) {
        // synchronous send; exception thrown on failure
        // Send rawOrderId and source as message headers
        jmsTemplate.convertAndSend(queueName, payload, message -> {
            message.setStringProperty("rawOrderId", rawOrderId.toString());
            message.setStringProperty("source", source);  // MQ or S3
            return message;
        });
    }
}
