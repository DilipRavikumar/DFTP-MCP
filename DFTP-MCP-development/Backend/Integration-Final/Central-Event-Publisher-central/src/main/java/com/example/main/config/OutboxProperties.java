package com.example.main.config;



import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "outbox")
public class OutboxProperties {

    /**
     * The fully qualified outbox table/collection name in the microservice DB.
     * Example: outbox_order_service (for JDBC) or outbox_events (for MongoDB)
     */
    private String tableName;

    /** Database type: JDBC or MONGODB */
    private DatabaseType databaseType = DatabaseType.JDBC;

    /** polling interval in ms */
    private long pollingIntervalMs = 3000L;

    /** status values used by outbox (optional overrides) */
    private String pendingStatus = "PENDING";
    private String sentStatus = "SENT";

    /** ActiveMQ specific - provided by microservice via properties */
    private String brokerUrl;
    private String username;
    private String password;
    private String queueName;

    public enum DatabaseType {
        JDBC,
        MONGODB
    }
    
    // getters / setters
    public String getTableName() { return tableName; }
    public void setTableName(String tableName) { this.tableName = tableName; }
    public DatabaseType getDatabaseType() { return databaseType; }
    public void setDatabaseType(DatabaseType databaseType) { this.databaseType = databaseType; }
    public long getPollingIntervalMs() { return pollingIntervalMs; }
    public void setPollingIntervalMs(long pollingIntervalMs) { this.pollingIntervalMs = pollingIntervalMs; }
    public String getPendingStatus() { return pendingStatus; }
    public void setPendingStatus(String pendingStatus) { this.pendingStatus = pendingStatus; }
    public String getSentStatus() { return sentStatus; }
    public void setSentStatus(String sentStatus) { this.sentStatus = sentStatus; }

    public String getBrokerUrl() { return brokerUrl; }
    public void setBrokerUrl(String brokerUrl) { this.brokerUrl = brokerUrl; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    public String getQueueName() { return queueName; }
    public void setQueueName(String queueName) { this.queueName = queueName; }
}
