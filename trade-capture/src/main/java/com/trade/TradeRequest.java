package com.trade;

import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "Trade submission request")
public class TradeRequest {
    
    @Schema(description = "Trade name", example = "AAPL", required = true)
    private String name;
    
    @Schema(description = "Number of shares", example = "100", required = true)
    private int quantity;
    
    @Schema(description = "Price per share", example = "150.50", required = true)
    private double price;
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public int getQuantity() { return quantity; }
    public void setQuantity(int quantity) { this.quantity = quantity; }
    
    public double getPrice() { return price; }
    public void setPrice(double price) { this.price = price; }
}