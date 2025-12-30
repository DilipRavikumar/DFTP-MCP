package com.example.dftp.model;

public class S3Notification {
    private String bucket;
    private String key;
    private Long size;
    private String md5;
    private String eventTime;

    // getters/setters
    public String getBucket() { return bucket; }
    public void setBucket(String bucket) { this.bucket = bucket; }
    public String getKey() { return key; }
    public void setKey(String key) { this.key = key; }
    public Long getSize() { return size; }
    public void setSize(Long size) { this.size = size; }
    public String getMd5() { return md5; }
    public void setMd5(String md5) { this.md5 = md5; }
    public String getEventTime() { return eventTime; }
    public void setEventTime(String eventTime) { this.eventTime = eventTime; }
}
