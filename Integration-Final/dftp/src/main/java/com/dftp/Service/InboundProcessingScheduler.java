package com.dftp.Service;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;

@Component
@RequiredArgsConstructor
@Slf4j
public class InboundProcessingScheduler {

    private final SafeInboundQueue queue;
    private final OrderIngestService ingestService;

    @Scheduled(fixedDelay = 1000) 
    public void pollAndProcess() {

        String msg;
        while ((msg = queue.poll()) != null) {   
            try {
                ingestService.ingestFromMq(msg);     
            } catch (Exception e) {
                // Log error but continue processing other messages
                log.error("Failed to process message: {}", msg, e);
            }
        }
    }
}
