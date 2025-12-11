package com.dfpt.canonical;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class CanonicalServiceApplication implements CommandLineRunner {

    private static final Logger logger = LoggerFactory.getLogger(CanonicalServiceApplication.class);
    
    @Value("${aws.sqs.enabled:false}")
    private boolean sqsEnabled;
    
    @Value("${aws.sqs.queue-name:simulator-trade-queue}")
    private String queueName;
    
    @Value("${aws.s3.bucket.name:simulator-trade-bucket}")
    private String bucketName;

    public static void main(String[] args) {
        SpringApplication.run(CanonicalServiceApplication.class, args);
    }

    @Override
    public void run(String... args) throws Exception {
        logger.info("=".repeat(60));
        logger.info("📡 CANONICAL SERVICE - AWS CONFIGURATION STATUS");
        logger.info("=".repeat(60));
        logger.info("🔧 SQS Enabled: {}", sqsEnabled);
        logger.info("📩 SQS Queue Name: {}", queueName);
        logger.info("🪣 S3 Bucket Name: {}", bucketName);
        
        if (sqsEnabled) {
            logger.info("✅ S3 File Processing via SQS is ENABLED");
            logger.info("🎯 Waiting for file upload notifications from Trade Simulator...");
        } else {
            logger.warn("⚠️ S3 File Processing via SQS is DISABLED");
            logger.warn("💡 Files uploaded to S3 will NOT be automatically processed");
            logger.warn("🔧 To enable: set aws.sqs.enabled=true in application.yml");
        }
        logger.info("=".repeat(60));
    }
}
