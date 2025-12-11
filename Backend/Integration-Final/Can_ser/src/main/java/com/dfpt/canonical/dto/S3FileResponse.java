package com.dfpt.canonical.dto;
public class S3FileResponse {
    private String status;
    private String message;
    private String error;
    public S3FileResponse() {
    }
    public S3FileResponse(String status, String message) {
        this.status = status;
        this.message = message;
    }
    public static S3FileResponse success(String message) {
        return new S3FileResponse("success", message);
    }
    public static S3FileResponse accepted(String message) {
        return new S3FileResponse("accepted", message);
    }
    public static S3FileResponse error(String errorMessage) {
        S3FileResponse response = new S3FileResponse();
        response.setStatus("error");
        response.setError(errorMessage);
        return response;
    }
    public String getStatus() {
        return status;
    }
    public void setStatus(String status) {
        this.status = status;
    }
    public String getMessage() {
        return message;
    }
    public void setMessage(String message) {
        this.message = message;
    }
    public String getError() {
        return error;
    }
    public void setError(String error) {
        this.error = error;
    }
}
