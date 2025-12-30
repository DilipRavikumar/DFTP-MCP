package com.example.dftp.model;

public class GenericAck {
    private String status;
    private String ref;

    public GenericAck() {}
    public GenericAck(String status, String ref) { this.status = status; this.ref = ref; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getRef() { return ref; }
    public void setRef(String ref) { this.ref = ref; }
}

