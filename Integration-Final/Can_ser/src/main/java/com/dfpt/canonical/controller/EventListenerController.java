package com.dfpt.canonical.controller;
import com.dfpt.canonical.dto.FileMetadataEvent;
import com.dfpt.canonical.service.S3FileProcessorService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jms.annotation.JmsListener;
import org.springframework.stereotype.Component;
@Component
public class EventListenerController {
    private static final Logger logger = LoggerFactory.getLogger(EventListenerController.class);
    @Autowired
    private S3FileProcessorService s3FileProcessorService;
    @Autowired
    private ObjectMapper objectMapper;
    @JmsListener(destination = "${jms.queue.file-upload}", concurrency = "5-10")
    public void handleFileUploadEvent(String message) {
        logger.info("Received ActiveMQ message: {}", message);
        try {
            FileMetadataEvent event = objectMapper.readValue(message, FileMetadataEvent.class);
            logger.info("Processing file upload event - S3 Key: {}, File: {}, Size: {} bytes", 
                event.getS3Key(), event.getFileName(), event.getFileSize());
            s3FileProcessorService.processS3File(event.getS3Key());
            logger.info("File processing initiated successfully for: {}", event.getFileName());
        } catch (Exception e) {
            logger.error("Error processing ActiveMQ message: {}", message, e);
        }
    }
}
