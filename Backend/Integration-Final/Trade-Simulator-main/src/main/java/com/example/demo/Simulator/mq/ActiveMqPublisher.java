package com.example.demo.Simulator.mq;

import org.apache.activemq.ActiveMQConnectionFactory;
import org.apache.activemq.ActiveMQConnection;
import org.apache.activemq.ActiveMQSession;
import org.apache.activemq.command.ActiveMQQueue;
import org.apache.activemq.command.ActiveMQTextMessage;

public class ActiveMqPublisher implements AutoCloseable {

    private final String brokerUrl;
    private final String queueName;
    private ActiveMQConnectionFactory connectionFactory;
    private ActiveMQConnection connection;
    private ActiveMQSession session;
    private org.apache.activemq.ActiveMQMessageProducer producer;

    public ActiveMqPublisher(String brokerUrl, String queueName) {
        this.brokerUrl = brokerUrl;
        this.queueName = queueName;
    }

    public void connect() throws Exception {
        connectionFactory = new ActiveMQConnectionFactory(brokerUrl);
        connection = (ActiveMQConnection) connectionFactory.createConnection();
        connection.start();

        session = (ActiveMQSession) connection.createSession(false, ActiveMQSession.AUTO_ACKNOWLEDGE);
        ActiveMQQueue destination = new ActiveMQQueue(queueName);
        producer = (org.apache.activemq.ActiveMQMessageProducer) session.createProducer(destination);
    }

    public void publish(String text) throws Exception {
        if (connection == null || session == null || producer == null) {
            throw new IllegalStateException("Not connected to ActiveMQ");
        }
        ActiveMQTextMessage message = (ActiveMQTextMessage) session.createTextMessage(text);
        producer.send(message);
    }

    @Override
    public void close() throws Exception {
        if (producer != null)
            producer.close();
        if (session != null)
            session.close();
        if (connection != null)
            connection.close();
    }
}