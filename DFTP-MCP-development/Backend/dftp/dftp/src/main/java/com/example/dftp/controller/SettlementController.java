package com.example.dftp.controller;

import com.example.dftp.model.GenericAck;
import com.example.dftp.model.SettlementStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.UUID;

@RestController
@RequestMapping("/api/settlement")
public class SettlementController {

    @PostMapping("/{tradeId}/confirm")
    public ResponseEntity<GenericAck> confirm(@PathVariable String tradeId) {
        String confirmId = "CONF-" + UUID.randomUUID().toString().substring(0,8);
        return ResponseEntity.ok(new GenericAck("CONFIRMED", confirmId));
    }

    @PostMapping("/{tradeId}/settle")
    public ResponseEntity<GenericAck> settle(@PathVariable String tradeId) {
        String settleId = "SETTLE-" + UUID.randomUUID().toString().substring(0,8);
        return ResponseEntity.ok(new GenericAck("SETTLED", settleId));
    }


    @GetMapping("/{tradeId}/status")
    public ResponseEntity<SettlementStatus> status(@PathVariable String tradeId) {
        boolean settled = tradeId.hashCode() % 2 == 0;
        SettlementStatus s = new SettlementStatus();
        s.setTradeId(tradeId);
        s.setStatus(settled ? "SETTLED" : "CONFIRMED");
        s.setUpdatedAt(LocalDateTime.now());
        return ResponseEntity.ok(s);
    }
}
