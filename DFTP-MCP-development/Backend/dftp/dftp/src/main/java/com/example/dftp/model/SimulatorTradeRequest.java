package com.example.dftp.model;

public class SimulatorTradeRequest {
    private String instrument;
    private String side; // BUY/SELL
    private Double quantity;
    private Double price;
    private String clientId;
    private String outputChannel; // MQ or S3

    public String getInstrument() { return instrument; }
    public void setInstrument(String instrument) { this.instrument = instrument; }
    public String getSide() { return side; }
    public void setSide(String side) { this.side = side; }
    public Double getQuantity() { return quantity; }
    public void setQuantity(Double quantity) { this.quantity = quantity; }
    public Double getPrice() { return price; }
    public void setPrice(Double price) { this.price = price; }
    public String getClientId() { return clientId; }
    public void setClientId(String clientId) { this.clientId = clientId; }
    public String getOutputChannel() { return outputChannel; }
    public void setOutputChannel(String outputChannel) { this.outputChannel = outputChannel; }
}
