package com.example.dftp.controller;

import com.example.dftp.model.*;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/positions")
public class PositionController {

    // 1️⃣ Send order data
    @PostMapping("/order")
    public ResponseEntity<OrderRequest> receiveOrder(@RequestBody OrderRequest order) {

        if (order.getTransactionId() == null) {
            order.setTransactionId("TXN-" + UUID.randomUUID().toString().substring(0, 8));
        }

        order.setReceivedAt(LocalDateTime.now());
        return ResponseEntity.ok(order);
    }

    // 2️⃣ Get NAV (mock)
    @GetMapping("/nav")
    public ResponseEntity<NavResponse> getNav(
            @RequestParam(required = false) Integer fundNumber,
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
            LocalDate asOfDate) {

        int fund = (fundNumber != null) ? fundNumber : 101;
        LocalDate date = (asOfDate != null) ? asOfDate : LocalDate.now();

        List<NavSecurity> mockSecurities = List.of(
                new NavSecurity("EQUITY-AAA", new BigDecimal("123.45")),
                new NavSecurity("DEBT-BBB", new BigDecimal("98.10")),
                new NavSecurity("CASH", new BigDecimal("1.00"))
        );

        NavResponse response = new NavResponse();
        response.setFundNumber(fund);
        response.setAsOfDate(date);
        response.setFileName("mock-nav-" + fund + "-" + date + ".csv");
        response.setTotalSecurities(mockSecurities.size());
        response.setSecurities(mockSecurities);

        return ResponseEntity.ok(response);
    }

    // 3️⃣ Calculate position from order + nav
    @PostMapping("/calculate")
    public ResponseEntity<PositionResponse> calculate(@RequestBody PositionCalculationRequest req) {

        OrderRequest order = req.getOrder();
        NavResponse nav = req.getNav();
        BigDecimal orderAmount = order.getDollarAmount() != null
                ? order.getDollarAmount() : new BigDecimal("10000");

        // Build mock response
        PositionResponse resp = new PositionResponse();
        resp.setPositionId(UUID.randomUUID());
        resp.setFundNumber(order.getFundNumber());
        resp.setClientName(order.getClientName());
        resp.setAsOfDate(nav.getAsOfDate());
        resp.setTotalValue(orderAmount);
        resp.setShareQuantity(orderAmount.divide(new BigDecimal("100"), BigDecimal.ROUND_HALF_UP));

        // mock holdings allocation
        List<Holding> holdings = List.of(
                new Holding(nav.getSecurities().get(0).getSecurityId(),
                        orderAmount.multiply(new BigDecimal("0.60")), 60),
                new Holding(nav.getSecurities().get(1).getSecurityId(),
                        orderAmount.multiply(new BigDecimal("0.30")), 30),
                new Holding(nav.getSecurities().get(2).getSecurityId(),
                        orderAmount.multiply(new BigDecimal("0.10")), 10)
        );

        resp.setHoldings(holdings);

        return ResponseEntity.ok(resp);
    }
}
