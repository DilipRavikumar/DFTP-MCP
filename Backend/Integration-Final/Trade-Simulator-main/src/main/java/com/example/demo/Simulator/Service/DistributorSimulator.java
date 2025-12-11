package com.example.demo.Simulator.Service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import com.example.demo.Simulator.mq.ActiveMqPublisher;

import java.util.List;

@Service
public class DistributorSimulator {

    private final ActiveMqPublisher mqPublisher;
    private final OrderGenerator orderGenerator;
    private List<String> generatedOrders;
    private int currentIndex = 0;

    @Autowired
    public DistributorSimulator(ActiveMqPublisher mqPublisher, OrderGenerator orderGenerator) {
        this.mqPublisher = mqPublisher;
        this.orderGenerator = orderGenerator;
        this.generatedOrders = orderGenerator.generateRandomOrders(20); 
    }

    public void sendOrder() throws Exception {
        mqPublisher.publish(generatedOrders.get(currentIndex % generatedOrders.size()));
        currentIndex++;
    }

    public void sendOrders(int count) throws Exception {
        for (int i = 0; i < count; i++) {
            sendOrder();
        }
    }

    public void send100Orders() throws Exception {
        System.out.println("Sending 100 orders (20 unique orders × 5 times) to MQ...");
        for (int batch = 0; batch < 5; batch++) {
            for (String order : generatedOrders) {
                mqPublisher.publish(order);
            }
            System.out.println("Batch " + (batch + 1) + " completed - 20 orders sent");
        }
        System.out.println("Successfully sent 100 orders to MQ.");
    }

    public void regenerateOrders() {
        this.generatedOrders = orderGenerator.generateRandomOrders(20);
        this.currentIndex = 0;
        System.out.println("Generated 20 new random orders");
    }

    public int getGeneratedOrdersCount() {
        return generatedOrders.size();
    }
}