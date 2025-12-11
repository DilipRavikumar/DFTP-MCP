package com.dfpt.canonical.service;

import com.dfpt.canonical.dto.ProcessingResult;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.awspring.cloud.sqs.annotation.SqsListener;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.channels.Channels;
import java.nio.channels.ReadableByteChannel;
import java.util.UUID;

/**
 * Listens to SQS queue for S3 file metadata
 * Downloads file from S3 and processes using existing TradeProcessingService
 */
@Component
@ConditionalOnProperty(name = "aws.sqs.enabled", havingValue = "true", matchIfMissing = false)
public class S3FileMetadataListener {
    
    private static final Logger logger = LoggerFactory.getLogger(S3FileMetadataListener.class);
    
    // Constructor logging to confirm bean creation
    public S3FileMetadataListener() {
        logger.info("🚀 S3FileMetadataListener initialized and ready to listen for SQS messages!");
    }
    
    @Autowired
    private S3Client s3Client;
    
    @Autowired
    private TradeProcessingService tradeProcessingService;
    
    @Value("${aws.s3.bucket.name:simulator-trade-bucket}")
    private String bucketName;
    
    private final ObjectMapper objectMapper = new ObjectMapper();
    
    /**
     * Listen to SQS queue for S3 file upload notifications
     * Message format: { "bucket": "...", "key": "incoming/file.txt", "size": 12345 }
     */
    @SqsListener("${aws.sqs.queue-name:simulator-trade-queue}")
    public void handleS3FileMetadata(String message) {
        logger.info("📥 Received SQS message: {}", message);
        
        try {
            // Parse SQS message to extract S3 metadata
            JsonNode messageJson = objectMapper.readTree(message);
            
            String bucket = extractBucket(messageJson);
            String key = extractKey(messageJson);
            
            if (bucket == null || key == null) {
                logger.error("❌ Invalid SQS message - missing bucket or key");
                return;
            }
            
            logger.info("📂 Processing S3 file: s3://{}/{}", bucket, key);
            
            // For S3 flow: fileId = raw_order_id from ingestion (represents the file batch)
            // Each trade will get its own UUID as rawOrderId (order_id)
            UUID fileId = UUID.randomUUID();  // This represents the file batch
            String source = "S3";
            logger.info("🆔 Generated fileId for S3 file: {}, source: {}", fileId, source);
            
            // Download file from S3
            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(bucket)
                    .key(key)
                    .build();
            
            // Use S3 InputStream with NIO Channel
            try (InputStream s3InputStream = s3Client.getObject(getObjectRequest);
                 ReadableByteChannel channel = Channels.newChannel(s3InputStream)) {
                
                String fileName = key.substring(key.lastIndexOf('/') + 1);
                logger.info("⬇️ Downloaded file from S3: {}", fileName);
                
                // Process file using existing NIO channel processing
                ProcessingResult result = tradeProcessingService.processTradeFileFromChannel(
                        channel, 
                        fileName,
                        fileId,  // Pass the fileId
                        source  // Pass the source
                );
                
                logger.info("✅ File processing completed: {} - Status: {} - Success: {}/{}", 
                    fileName, result.getStatus(), result.getSuccessCount(), result.getTotalRecords());
                
            }
            
        } catch (Exception e) {
            logger.error("❌ Error processing S3 file from SQS message", e);
            throw new RuntimeException("Failed to process S3 file", e);
        }
    }
    
    /**
     * Extract S3 bucket from SQS message
     * Handles both direct format and S3 event notification format
     */
    private String extractBucket(JsonNode messageJson) {
        // Direct format: { "bucket": "name" }
        if (messageJson.has("bucket")) {
            return messageJson.get("bucket").asText();
        }
        
        // S3 Event Notification format: { "Records": [{ "s3": { "bucket": { "name": "..." } } }] }
        if (messageJson.has("Records")) {
            JsonNode records = messageJson.get("Records");
            if (records.isArray() && records.size() > 0) {
                JsonNode firstRecord = records.get(0);
                if (firstRecord.has("s3")) {
                    JsonNode s3 = firstRecord.get("s3");
                    if (s3.has("bucket") && s3.get("bucket").has("name")) {
                        return s3.get("bucket").get("name").asText();
                    }
                }
            }
        }
        
        // Fallback to configured bucket
        return bucketName;
    }
    
    /**
     * Extract S3 key from SQS message
     * Handles both direct format and S3 event notification format
     */
    private String extractKey(JsonNode messageJson) {
        // Direct format: { "key": "path/to/file.txt" }
        if (messageJson.has("key")) {
            return messageJson.get("key").asText();
        }
        
        // S3 Event Notification format: { "Records": [{ "s3": { "object": { "key": "..." } } }] }
        if (messageJson.has("Records")) {
            JsonNode records = messageJson.get("Records");
            if (records.isArray() && records.size() > 0) {
                JsonNode firstRecord = records.get(0);
                if (firstRecord.has("s3")) {
                    JsonNode s3 = firstRecord.get("s3");
                    if (s3.has("object") && s3.get("object").has("key")) {
                        return s3.get("object").get("key").asText();
                    }
                }
            }
        }
        
        return null;
    }
}
