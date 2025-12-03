package com.trade;

import org.springframework.web.bind.annotation.*;
import java.util.Map;
import java.util.HashMap;

@RestController
public class FraudController {
    
    @GetMapping("/")
    public Map<String, String> home() {
        Map<String, String> response = new HashMap<>();
        response.put("service", "Fraud Service (DUMMY)");
        response.put("status", "Running");
        response.put("port", "8082");
        response.put("mode", "Always approves trades");
        return response;
    }
    
    @GetMapping("/health")
    public Map<String, String> health() {
        Map<String, String> response = new HashMap<>();
        response.put("status", "UP");
        response.put("service", "Fraud Service");
        return response;
    }
}