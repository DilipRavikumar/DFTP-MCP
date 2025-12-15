package com.example.dftp.controller;

import com.example.dftp.model.*;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.UUID;

@RestController
@RequestMapping("/api/canonical")
public class CanonicalController {

    @PostMapping("/parse")
    public ResponseEntity<ParseResult> parse(@RequestBody ParseRequest req) {
        // simple mock logic: if payload hint contains "BAD" -> return exception
        if (req.getFormatHint() != null && req.getFormatHint().toUpperCase().contains("BAD")) {
            ExceptionDTO ex = new ExceptionDTO("EX-" + UUID.randomUUID().toString().substring(0,8),
                    "canonical", req.getReferenceId(), "PARSE_ERR", "Failed parsing - format invalid", "HIGH", 0.0, "OPEN");
            return ResponseEntity.ok(new ParseResult(null, ex));
        }

        // Otherwise build a canonical trade DTO
        CanonicalTrade canonical = new CanonicalTrade();
        canonical.setTradeId("T-" + UUID.randomUUID().toString().substring(0,8));
        canonical.setTradeDate(req.getTradeDate() != null ? req.getTradeDate() : LocalDate.now());
        canonical.setSettlementDate(req.getSettlementDate() != null ? req.getSettlementDate() : LocalDate.now().plusDays(2));
        canonical.setAssetType("EQUITY");
        canonical.setAssetId("ASSET-XYZ");
        canonical.setTradeAmount(req.getTradeAmount() != null ? req.getTradeAmount() : req.getDefaultAmount());
        canonical.setTradeVolume(req.getTradeVolume() != null ? req.getTradeVolume() : 100.0);
        canonical.setCurrency("INR");

        return ResponseEntity.ok(new ParseResult(canonical, null));
    }


    @GetMapping("/trade/{id}")
    public ResponseEntity<CanonicalTrade> getCanonical(@PathVariable String id) {
        CanonicalTrade c = new CanonicalTrade();
        c.setTradeId(id);
        c.setTradeDate(LocalDate.now());
        c.setSettlementDate(LocalDate.now().plusDays(2));
        c.setAssetType("EQUITY");
        c.setAssetId("ASSET-XYZ");
        c.setTradeAmount(10000.0);
        c.setTradeVolume(100.0);
        c.setCurrency("INR");
        return ResponseEntity.ok(c);
    }
}
