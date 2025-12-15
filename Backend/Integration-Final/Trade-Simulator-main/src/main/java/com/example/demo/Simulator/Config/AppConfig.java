package com.example.demo.Simulator.Config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import com.example.demo.Simulator.mq.ActiveMqPublisher;

@Configuration
public class AppConfig {

    @Bean
    public ActiveMqPublisher activeMqPublisher(@Value("${spring.activemq.broker-url}") String brokerUrl)
            throws Exception {
        ActiveMqPublisher publisher = new ActiveMqPublisher(brokerUrl, "orderdata.mq");
        publisher.connect();
        return publisher;
    }
}