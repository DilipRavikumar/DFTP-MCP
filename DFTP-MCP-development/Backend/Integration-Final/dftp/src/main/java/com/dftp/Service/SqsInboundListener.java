package com.dftp.Service;
import org.springframework.stereotype.Component;

import io.awspring.cloud.sqs.annotation.SqsListener;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Slf4j
@Component
@RequiredArgsConstructor
public class SqsInboundListener {

     private final OrderIngestService ingestService;

    @SqsListener("${aws.sqs.queue-name}")
    public void handleSqsMessage(String payload) {

        log.info("Received SQS message: {}", payload);
        ingestService.ingestFromSqs(payload);
    }
}