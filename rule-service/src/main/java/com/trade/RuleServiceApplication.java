package com.trade;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.jms.annotation.EnableJms;

@SpringBootApplication
public class RuleServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(RuleServiceApplication.class, args);
    }
}