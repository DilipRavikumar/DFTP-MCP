package com.example.main.listener;


import org.springframework.jms.annotation.JmsListener;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class GenericJmsListener {

    private final List<Object> receivedMessages = new ArrayList<>();

    @JmsListener(destination = "${outbox.queue-name}")   // <-- placeholder
    public void listen(Object message) {
        receivedMessages.add(message);
        System.out.println("Received message: " + message);
    }

    public List<Object> getReceivedMessages() {
        return receivedMessages;
    }
}