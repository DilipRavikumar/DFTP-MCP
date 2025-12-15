package com.dfpt.canonical.dto;
public class FileMetadataEvent {
    private String s3Bucket;
    private String s3Key;
    private String fileName;
    private Long fileSize;
    private String contentType;
    private String eventType;
    private String timestamp;
    public String getS3Bucket() {
        return s3Bucket;
    }
    public void setS3Bucket(String s3Bucket) {
        this.s3Bucket = s3Bucket;
    }
    public String getS3Key() {
        return s3Key;
    }
    public void setS3Key(String s3Key) {
        this.s3Key = s3Key;
    }
    public String getFileName() {
        return fileName;
    }
    public void setFileName(String fileName) {
        this.fileName = fileName;
    }
    public Long getFileSize() {
        return fileSize;
    }
    public void setFileSize(Long fileSize) {
        this.fileSize = fileSize;
    }
    public String getContentType() {
        return contentType;
    }
    public void setContentType(String contentType) {
        this.contentType = contentType;
    }
    public String getEventType() {
        return eventType;
    }
    public void setEventType(String eventType) {
        this.eventType = eventType;
    }
    public String getTimestamp() {
        return timestamp;
    }
    public void setTimestamp(String timestamp) {
        this.timestamp = timestamp;
    }
}
