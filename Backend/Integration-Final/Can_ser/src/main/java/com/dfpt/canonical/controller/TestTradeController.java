package com.dfpt.canonical.controller;

import com.dfpt.canonical.dto.ProcessingResult;
import com.dfpt.canonical.service.TradeProcessingService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.util.UUID;

@RestController
@RequestMapping("/api/test")
public class TestTradeController {
    
    private static final Logger logger = LoggerFactory.getLogger(TestTradeController.class);
    
    @Autowired
    private TradeProcessingService tradeProcessingService;
    
    @PostMapping("/upload-trade-file")
    public ResponseEntity<?> uploadTradeFile(@RequestParam("file") MultipartFile file) {
        try {
            if (file.isEmpty()) {
                return ResponseEntity.badRequest().body("File is empty");
            }
            
            // Create temp file
            String tempFileName = "temp_" + UUID.randomUUID() + "_" + file.getOriginalFilename();
            File tempFile = new File(System.getProperty("java.io.tmpdir"), tempFileName);
            
            // Save uploaded file to temp location
            try (FileOutputStream fos = new FileOutputStream(tempFile)) {
                fos.write(file.getBytes());
            }
            
            logger.info("Processing uploaded file: {} (size: {} bytes)", file.getOriginalFilename(), file.getSize());
            
            // Process file using TradeProcessingService
            ProcessingResult result;
            try (FileChannel channel = FileChannel.open(tempFile.toPath(), StandardOpenOption.READ)) {
                result = tradeProcessingService.processTradeFileFromChannel(
                    channel, 
                    tempFileName, 
                    UUID.randomUUID(), 
                    "UPLOAD"
                );
            }
            
            // Clean up temp file
            try {
                Files.deleteIfExists(tempFile.toPath());
            } catch (Exception e) {
                logger.warn("Failed to delete temp file: {}", tempFile.getName());
            }
            
            logger.info("Trade file processing completed: {} trades processed, {} successful, {} failed", 
                       result.getTotalRecords(), result.getSuccessCount(), result.getFailedCount());
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            logger.error("Error processing trade file upload", e);
            return ResponseEntity.internalServerError().body("Error: " + e.getMessage());
        }
    }
    
    @PostMapping("/process-sample")
    public ResponseEntity<?> processSampleFile() {
        try {
            // Use the sample file from resources
            File sampleFile = new File("sample-files/sample-trades.txt");
            if (!sampleFile.exists()) {
                sampleFile = new File("src/main/resources/sample-trades.txt");
            }
            if (!sampleFile.exists()) {
                return ResponseEntity.notFound().build();
            }
            
            logger.info("Processing sample file: {}", sampleFile.getName());
            
            // Process file using TradeProcessingService
            ProcessingResult result;
            try (FileChannel channel = FileChannel.open(sampleFile.toPath(), StandardOpenOption.READ)) {
                result = tradeProcessingService.processTradeFileFromChannel(
                    channel, 
                    sampleFile.getName(), 
                    UUID.randomUUID(), 
                    "SAMPLE_TEST"
                );
            }
            
            logger.info("Sample file processing completed: {} trades processed, {} successful, {} failed", 
                       result.getTotalRecords(), result.getSuccessCount(), result.getFailedCount());
            
            return ResponseEntity.ok(result);
            
        } catch (Exception e) {
            logger.error("Error processing sample file", e);
            return ResponseEntity.internalServerError().body("Error: " + e.getMessage());
        }
    }
}