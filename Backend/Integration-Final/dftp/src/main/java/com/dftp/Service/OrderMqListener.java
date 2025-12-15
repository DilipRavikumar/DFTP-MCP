package com.dftp.Service;

import org.springframework.jms.annotation.JmsListener;
import org.springframework.stereotype.Component;

@Component
public class OrderMqListener {

    private final SafeInboundQueue safeQueue;

    public OrderMqListener(SafeInboundQueue safeQueue) {
        this.safeQueue = safeQueue;
    }

    @JmsListener(destination = "orderdata.mq")
    public void receiveMessage(String msg) {
        System.out.println("<<<< RECEIVED FROM MQ >>>> " + msg);
        safeQueue.push(msg);
    }
}
