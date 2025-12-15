package com.dfpt.canonical.controller;
import com.dfpt.canonical.dto.FileMetadataEvent;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.web.bind.annotation.*;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
@RestController
@RequestMapping("/api/test")
public class TestPublisherController {
    private static final Logger logger = LoggerFactory.getLogger(TestPublisherController.class);
    @Autowired
    private JmsTemplate jmsTemplate;
    @Autowired
    private ObjectMapper objectMapper;
    @Value("${jms.queue.file-upload}")
    private String fileUploadQueue;
    @PostMapping("/publish-event")
    public String publishFileUploadEvent(@RequestBody FileMetadataEvent event) {
        try {
            if (event.getS3Bucket() == null) {
                event.setS3Bucket("dftpioioio");
            }
            if (event.getFileName() == null && event.getS3Key() != null) {
                event.setFileName(event.getS3Key().substring(event.getS3Key().lastIndexOf('/') + 1));
            }
            if (event.getEventType() == null) {
                event.setEventType("FILE_UPLOADED");
            }
            if (event.getTimestamp() == null) {
                event.setTimestamp(LocalDateTime.now().format(DateTimeFormatter.ISO_DATE_TIME));
            }
            String jsonMessage = objectMapper.writeValueAsString(event);
            logger.info("Publishing event to ActiveMQ queue '{}': {}", fileUploadQueue, jsonMessage);
            jmsTemplate.convertAndSend(fileUploadQueue, jsonMessage);
            logger.info("Event published successfully");
            return "Event published to queue: " + fileUploadQueue + "\nMessage: " + jsonMessage;
        } catch (Exception e) {
            logger.error("Error publishing event", e);
            return "Error: " + e.getMessage();
        }
    }
    @PostMapping("/quick-publish")
    public String quickPublish(@RequestParam String s3Key) {
        FileMetadataEvent event = new FileMetadataEvent();
        event.setS3Key(s3Key);
        return publishFileUploadEvent(event);
    }
}
