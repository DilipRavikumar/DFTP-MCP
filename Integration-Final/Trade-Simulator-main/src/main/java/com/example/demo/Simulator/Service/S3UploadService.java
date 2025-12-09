package com.example.demo.Simulator.Service;

import java.io.File;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;

import java.util.HashMap;
import java.util.Map;

@Service
@ConditionalOnProperty(name = "aws.s3.enabled", havingValue = "true", matchIfMissing = false)
public class S3UploadService {

    private final S3Client s3Client;
    
    @Autowired(required = false)
    private SqsClient sqsClient;

    @Value("${app.s3.bucket}")
    private String bucket;
    
    @Value("${aws.sqs.queue-url:}")
    private String queueUrl;
    
    @Value("${aws.sqs.enabled:false}")
    private boolean sqsEnabled;

    private final ObjectMapper objectMapper = new ObjectMapper();

    public S3UploadService(S3Client s3Client) {
        this.s3Client = s3Client;
    }

    public void uploadFile(File file, String key) throws Exception {
        System.out.println("Attempting to upload file: " + file.getName() + " to bucket: " + bucket + " with key: " + key);
        
        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build();

        s3Client.putObject(request, RequestBody.fromFile(file.toPath()));

        System.out.println("✅ Successfully uploaded to S3: " + key);
        
        // Send SQS notification after successful S3 upload
        if (sqsEnabled && sqsClient != null && queueUrl != null && !queueUrl.isEmpty()) {
            sendSqsNotification(bucket, key, file.length());
        } else {
            System.out.println("⚠️ SQS notification skipped - SQS not enabled or configured");
        }
    }

    public String uploadFileFromBytes(String key, byte[] content) throws Exception {
        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .build();

        s3Client.putObject(request, RequestBody.fromBytes(content));

        System.out.println("✅ Successfully uploaded bytes to S3: " + key);
        
        // Send SQS notification after successful S3 upload
        if (sqsEnabled && sqsClient != null && queueUrl != null && !queueUrl.isEmpty()) {
            sendSqsNotification(bucket, key, content.length);
        }

        return "https://" + bucket + ".s3.amazonaws.com/" + key;
    }
    
    private void sendSqsNotification(String bucket, String key, long size) {
        try {
            Map<String, Object> message = new HashMap<>();
            message.put("bucket", bucket);
            message.put("key", key);
            message.put("size", size);
            message.put("eventType", "s3:ObjectCreated");
            
            String messageBody = objectMapper.writeValueAsString(message);
            
            SendMessageRequest sendMsgRequest = SendMessageRequest.builder()
                    .queueUrl(queueUrl)
                    .messageBody(messageBody)
                    .build();
                    
            sqsClient.sendMessage(sendMsgRequest);
            System.out.println("📩 SQS notification sent: " + messageBody);
            
        } catch (Exception e) {
            System.err.println("❌ Failed to send SQS notification: " + e.getMessage());
        }
    }

}