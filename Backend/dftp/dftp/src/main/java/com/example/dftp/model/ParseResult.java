package com.example.dftp.model;

public class ParseResult {
    private CanonicalTrade canonicalTrade;
    private ExceptionDTO exception;

    public ParseResult() {}
    public ParseResult(CanonicalTrade canonicalTrade, ExceptionDTO exception) {
        this.canonicalTrade = canonicalTrade;
        this.exception = exception;
    }


    public CanonicalTrade getCanonicalTrade() { return canonicalTrade; }
    public void setCanonicalTrade(CanonicalTrade canonicalTrade) { this.canonicalTrade = canonicalTrade; }
    public ExceptionDTO getException() { return exception; }
    public void setException(ExceptionDTO exception) { this.exception = exception; }
}
