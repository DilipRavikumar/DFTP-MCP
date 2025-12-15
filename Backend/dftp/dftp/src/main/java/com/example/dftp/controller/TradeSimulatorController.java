package com.example.dftp.controller;

import com.example.dftp.model.SimulatorTradeRequest;
import com.example.dftp.model.SimulatorResult;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.UUID;

@RestController
@RequestMapping("/api/simulator")
public class TradeSimulatorController {


    @PostMapping("/trade")
    public ResponseEntity<SimulatorResult> createSimulatedTrade(@RequestBody SimulatorTradeRequest req) {
        String messageId = "MSG-" + UUID.randomUUID().toString().substring(0, 8);
        String s3Key = "s3://mock-bucket/trades/" + messageId + ".csv";
        SimulatorResult r = new SimulatorResult(messageId, s3Key, LocalDateTime.now());
        return ResponseEntity.ok(r);
    }
}
