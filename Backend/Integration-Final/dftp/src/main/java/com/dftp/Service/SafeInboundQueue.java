package com.dftp.Service;
import java.util.concurrent.ConcurrentLinkedQueue;

import org.springframework.stereotype.Component;

@Component
public class SafeInboundQueue {

    private final ConcurrentLinkedQueue<String> queue = new ConcurrentLinkedQueue<>();

    public void push(String msg) {
        queue.offer(msg);
    }

    public String poll() {
        return queue.poll();
    }

    public boolean isEmpty() {
        return queue.isEmpty();
    }

    public void add(String msg) {
        queue.add(msg);
    }
}
