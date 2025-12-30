package com.dfpt.canonical.dto;
import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlElementWrapper;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlProperty;
import com.fasterxml.jackson.dataformat.xml.annotation.JacksonXmlRootElement;
import java.util.List;
@JacksonXmlRootElement(localName = "Orders")
public class ExternalTradeListDTO {
    @JacksonXmlProperty(localName = "Order")
    @JacksonXmlElementWrapper(useWrapping = false)
    @JsonProperty("trades")  
    private List<ExternalTradeDTO> orders;
    public List<ExternalTradeDTO> getOrders() {
        return orders;
    }
    public void setOrders(List<ExternalTradeDTO> orders) {
        this.orders = orders;
    }
}
