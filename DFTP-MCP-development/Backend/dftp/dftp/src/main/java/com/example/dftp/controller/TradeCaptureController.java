package com.example.dftp.controller;

import com.example.dftp.model.RawTradeMessage;
import com.example.dftp.model.S3Notification;
import com.example.dftp.model.GenericAck;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.UUID;

@RestController
@RequestMapping("/api/trade-capture")
public class TradeCaptureController {


    @PostMapping("/mq")
    public ResponseEntity<GenericAck> captureFromMq(@RequestBody RawTradeMessage msg) {
        String captureId = "CAP-" + UUID.randomUUID().toString().substring(0, 8);
        msg.setCapturedAt(LocalDateTime.now());
        msg.setCaptureId(captureId);
        // In a real system: persist raw trade and push outbox event.
        return ResponseEntity.ok(new GenericAck("RECEIVED", captureId));
    }


    @PostMapping("/s3-notify")
    public ResponseEntity<GenericAck> captureFromS3(@RequestBody S3Notification n) {
        String captureId = "CAP-" + UUID.randomUUID().toString().substring(0, 8);
        return ResponseEntity.ok(new GenericAck("S3_RECEIVED", captureId));
    }
}
