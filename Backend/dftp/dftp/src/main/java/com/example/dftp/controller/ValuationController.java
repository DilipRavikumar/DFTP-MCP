package com.example.dftp.controller;

import com.example.dftp.model.*;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/valuation")
public class ValuationController {


    @GetMapping("/trade/{tradeId}")
    public ResponseEntity<ValuationResult> getValuation(@PathVariable String tradeId) {
        ValuationResult v = new ValuationResult();
        v.setTradeId(tradeId);
        v.setValuationId("VAL-" + UUID.randomUUID().toString().substring(0,8));
        v.setGrossAmount(new BigDecimal("1000.00"));
        v.setFees(new BigDecimal("5.00"));
        v.setNetAmount(new BigDecimal("995.00"));
        v.setCalculatedAt(LocalDateTime.now());
        return ResponseEntity.ok(v);
    }
}
