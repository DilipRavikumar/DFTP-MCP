package com.trade;

import org.springframework.web.bind.annotation.*;
import org.springframework.beans.factory.annotation.Autowired;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.Map;
import java.util.HashMap;
import java.util.List;

@RestController
@Tag(name = "Trade Processing", description = "Trade submission and processing API")
public class TradeController {
    
    @Autowired
    private TradeService tradeService;
    
    @PostMapping("/trade")
    @Operation(summary = "Submit Trade", description = "Submit a new trade for processing")
    public TradeResponse submitTrade(@RequestBody TradeRequest request) {
        Trade trade = tradeService.submitTrade(request.getName(), request.getQuantity(), request.getPrice());
        return new TradeResponse("RECEIVED", trade.getId().toString());
    }
    
    @GetMapping("/trades")
    @Operation(summary = "Get All Trades", description = "Retrieve all submitted trades")
    public List<Trade> getAllTrades() {
        return tradeService.getAllTrades();
    }
    
    @GetMapping("/trades/{id}")
    @Operation(summary = "Get Trade by ID", description = "Retrieve a specific trade by ID")
    public Trade getTradeById(@PathVariable Long id) {
        return tradeService.getTradeById(id);
    }
}