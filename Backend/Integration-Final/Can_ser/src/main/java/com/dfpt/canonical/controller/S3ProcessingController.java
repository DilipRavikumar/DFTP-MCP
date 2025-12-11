package com.dfpt.canonical.controller;
import com.dfpt.canonical.dto.S3FileRequest;
import com.dfpt.canonical.dto.S3FileResponse;
import com.dfpt.canonical.service.S3FileProcessorService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/s3")
public class S3ProcessingController {
    private static final Logger logger = LoggerFactory.getLogger(S3ProcessingController.class);
    @Autowired
    private S3FileProcessorService s3FileProcessorService;
    @PostMapping("/process")
    public ResponseEntity<S3FileResponse> processS3File(@RequestBody S3FileRequest request) {
        try {
            String s3Key = request.getS3Key();
            if (s3Key == null || s3Key.isEmpty()) {
                return ResponseEntity.badRequest()
                        .body(S3FileResponse.error("s3Key is required"));
            }
            s3FileProcessorService.processS3File(s3Key);
            return ResponseEntity.accepted()
                    .body(S3FileResponse.accepted("File processing started for: " + s3Key));
        } catch (Exception e) {
            logger.error("Error initiating S3 file processing", e);
            return ResponseEntity.internalServerError()
                    .body(S3FileResponse.error(e.getMessage()));
        }
    }
    @PostMapping("/process-sync")
    public ResponseEntity<S3FileResponse> processS3FileSync(@RequestBody S3FileRequest request) {
        try {
            String s3Key = request.getS3Key();
            if (s3Key == null || s3Key.isEmpty()) {
                return ResponseEntity.badRequest()
                        .body(S3FileResponse.error("s3Key is required"));
            }
            s3FileProcessorService.processS3FileSync(s3Key);
            return ResponseEntity.ok()
                    .body(S3FileResponse.success("File processed successfully: " + s3Key));
        } catch (Exception e) {
            logger.error("Error processing S3 file synchronously", e);
            return ResponseEntity.internalServerError()
                    .body(S3FileResponse.error(e.getMessage()));
        }
    }
}
