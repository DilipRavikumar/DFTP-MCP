package com.example.dftp.model;



public class PositionCalculationRequest {

    private OrderRequest order;
    private NavResponse nav;

    public OrderRequest getOrder() { return order; }
    public void setOrder(OrderRequest order) { this.order = order; }

    public NavResponse getNav() { return nav; }
    public void setNav(NavResponse nav) { this.nav = nav; }
}

