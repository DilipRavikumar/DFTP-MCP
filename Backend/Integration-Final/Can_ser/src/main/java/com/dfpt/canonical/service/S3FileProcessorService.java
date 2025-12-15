package com.dfpt.canonical.service;
import com.dfpt.canonical.dto.ProcessingResult;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.S3Exception;
import software.amazon.awssdk.core.ResponseInputStream;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import java.io.File;
import java.util.UUID;

import java.io.InputStream;
import java.nio.channels.Channels;
import java.nio.channels.ReadableByteChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
@Service
public class S3FileProcessorService {
    private static final Logger logger = LoggerFactory.getLogger(S3FileProcessorService.class);
    @Value("${aws.s3.bucket.name}")
    private String bucketName;
    @Value("${aws.s3.region:us-east-1}")
    private String region;
    @Value("${file.processing.threads:5}")
    private int processingThreads;
    @Value("${temp.directory:./temp}")
    private String tempDirectory;
    @Autowired
    private TradeProcessingService tradeProcessingService;
    private S3Client s3Client;
    private ExecutorService fileProcessingExecutor;
    @PostConstruct
    public void init() {
        fileProcessingExecutor = Executors.newFixedThreadPool(processingThreads);
        logger.info("S3 file processing thread pool initialized with {} threads", processingThreads);
        s3Client = S3Client.builder()
                .region(Region.of(region))
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
        File tempDir = new File(tempDirectory);
        if (!tempDir.exists()) {
            tempDir.mkdirs();
        }
        logger.info("S3 File Processor initialized for bucket: {}", bucketName);
    }
    @PreDestroy
    public void cleanup() {
        try {
            logger.info("Shutting down file processing executor...");
            fileProcessingExecutor.shutdown();
            if (!fileProcessingExecutor.awaitTermination(60, TimeUnit.SECONDS)) {
                fileProcessingExecutor.shutdownNow();
            }
            if (s3Client != null) {
                s3Client.close();
            }
            logger.info("S3 file processor shut down successfully");
        } catch (Exception e) {
            logger.error("Error during cleanup", e);
            fileProcessingExecutor.shutdownNow();
        }
    }
    public void processS3File(String s3Key) {
        fileProcessingExecutor.submit(() -> {
            String threadName = Thread.currentThread().getName();
            long startTime = System.currentTimeMillis();
            try {
                logger.info("[NIO APPROACH] Processing S3 file: {} on thread: {}", s3Key, threadName);
                processS3FileWithNIO(s3Key);
                long totalTime = System.currentTimeMillis() - startTime;
                logger.info("[NIO APPROACH] Total time: {} ms on thread: {}", totalTime, threadName);
            } catch (Exception e) {
                logger.error("Error processing S3 file: {} on thread: {}", s3Key, threadName, e);
            }
        });
    }
    private void processS3FileWithNIO(String s3Key) throws Exception {
        long streamStart = System.currentTimeMillis();
        GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                .bucket(bucketName)
                .key(s3Key)
                .build();
        try (ResponseInputStream<GetObjectResponse> s3Stream = s3Client.getObject(getObjectRequest);
             ReadableByteChannel channel = Channels.newChannel(s3Stream)) {
            String fileName = s3Key.substring(s3Key.lastIndexOf('/') + 1);
            long streamTime = System.currentTimeMillis() - streamStart;
            logger.info("[NIO APPROACH] Stream setup time: {} ms", streamTime);
            logger.info("[NIO APPROACH] Processing S3 file using NIO channels: {} from bucket: {}", fileName, bucketName);
            
            // Generate rawOrderId for S3 file
            UUID rawOrderId = UUID.randomUUID();
            String source = "S3";
            logger.info("[NIO APPROACH] Generated rawOrderId: {}, source: {}", rawOrderId, source);
            
            long processingStart = System.currentTimeMillis();
            ProcessingResult result = tradeProcessingService.processTradeFileFromChannel(channel, fileName, rawOrderId, source);
            long processingTime = System.currentTimeMillis() - processingStart;
            logger.info("[NIO APPROACH] Processing time: {} ms", processingTime);
            logger.info("[NIO APPROACH] Processed S3 file: {} - Status: {} - Success: {}/{} on thread: {}",
                    s3Key, result.getStatus(), result.getSuccessCount(),
                    result.getTotalRecords(), Thread.currentThread().getName());
        } catch (S3Exception e) {
            logger.error("S3 error processing file: {}", s3Key, e);
            throw new Exception("Failed to process from S3: " + e.getMessage(), e);
        }
    }
    private File downloadFromS3(String s3Key) throws Exception {
        try {
            String fileName = s3Key.substring(s3Key.lastIndexOf('/') + 1);
            Path tempFilePath = Path.of(tempDirectory, fileName);
            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(bucketName)
                    .key(s3Key)
                    .build();
            try (InputStream s3InputStream = s3Client.getObject(getObjectRequest)) {
                Files.copy(s3InputStream, tempFilePath, StandardCopyOption.REPLACE_EXISTING);
            }
            logger.info("Downloaded S3 file: {} to {}", s3Key, tempFilePath);
            return tempFilePath.toFile();
        } catch (S3Exception e) {
            logger.error("S3 error downloading file: {}", s3Key, e);
            throw new Exception("Failed to download from S3: " + e.getMessage(), e);
        }
    }
    public void processS3FileSync(String s3Key) throws Exception {
        File localFile = null;
        try {
            localFile = downloadFromS3(s3Key);
            ProcessingResult result = tradeProcessingService.processTradeFile(localFile.getAbsolutePath());
            logger.info("Sync processed: {} - Status: {}", s3Key, result.getStatus());
        } finally {
            if (localFile != null && localFile.exists()) {
                localFile.delete();
            }
        }
    }
}
