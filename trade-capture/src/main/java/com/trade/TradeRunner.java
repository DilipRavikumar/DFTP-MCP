package com.trade;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class TradeRunner implements CommandLineRunner {
    
    @Autowired
    private TradeService tradeService;
    
    @Override
    public void run(String... args) throws Exception {
        Thread.sleep(2000);
        
        tradeService.submitTrade("AAPL", 100, 150.0);
        tradeService.submitTrade("GOOGL", 50, 2500.0);
        tradeService.submitTrade("MSFT", -10, 300.0);
        
        Thread.sleep(10000);
    }
}