package com.example.status.controller;

import com.example.status.entity.OrderStateHistoryEntity;
import com.example.status.service.OrderStatusService;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Controller exposing endpoints for OrderStatusService methods.
 *
 * Endpoints included:
 *  - GET  /api/orders/{orderId}/status
 *  - GET  /api/orders/file/{fileId}
 *  - GET  /api/orders/file/{fileId}/exists
 *  - GET  /api/orders/file/{fileId}/history
 *  - GET  /api/orders/file/{fileId}/history/paged?page=&size=
 *  - GET  /api/orders/statuses/{state}
 *  - GET  /api/orders/statuses/{state}/paged?page=&size=
 *  - GET  /api/orders/statuses/{state}/count
 *  - GET  /api/orders/statuses/distinct
 */
@RestController
@RequestMapping("/api/orders")
public class OrderStatusController {

    private final OrderStatusService orderStatusService;

    public OrderStatusController(OrderStatusService orderStatusService) {
        this.orderStatusService = orderStatusService;
    }

    /**
     * GET /api/orders/{orderId}/status
     * Latest status for a given orderId
     */
    @GetMapping("/{orderId}/status")
    public ResponseEntity<OrderStateHistoryEntity> getOrderStatus(@PathVariable String orderId) {
        return orderStatusService.getLatestOrderStatus(orderId)
                .map(ResponseEntity::ok)
                .orElse(ResponseEntity.notFound().build());
    }

    /**
     * GET /api/orders/file/{fileId}
     * Latest status for a given fileId
     */
    @GetMapping("/file/{fileId}")
    public ResponseEntity<OrderStateHistoryEntity> getStatusByFileId(@PathVariable String fileId) {
        return orderStatusService.getLatestByFileId(fileId)
                .map(entity -> new ResponseEntity<>(entity, HttpStatus.OK))
                .orElseGet(() -> new ResponseEntity<>(HttpStatus.NOT_FOUND));
    }

    /**
     * GET /api/orders/file/{fileId}/exists
     * Returns true/false whether the fileId has been seen.
     */
    @GetMapping("/file/{fileId}/exists")
    public ResponseEntity<Boolean> fileExists(@PathVariable("fileId") String fileId) {
        boolean exists = orderStatusService.fileExists(fileId);
        return ResponseEntity.ok(exists);
    }

    /**
     * GET /api/orders/file/{fileId}/history
     * Returns full history list for a fileId (descending by eventTime).
     */
    @GetMapping("/file/{fileId}/history")
    public ResponseEntity<?> getHistoryByFileId(@PathVariable("fileId") String fileId) {
        List<OrderStateHistoryEntity> history = orderStatusService.getHistoryByFileId(fileId);
        if (history == null || history.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body("No history found for fileId: " + fileId);
        }
        return ResponseEntity.ok(history);
    }

    /**
     * GET /api/orders/file/{fileId}/history/paged?page=0&size=20
     * Returns a Page<OrderStateHistoryEntity>.
     */
    @GetMapping("/file/{fileId}/history/paged")
    public ResponseEntity<?> getHistoryByFileIdPaged(
            @PathVariable("fileId") String fileId,
            @RequestParam(name = "page", required = false, defaultValue = "0") int page,
            @RequestParam(name = "size", required = false, defaultValue = "20") int size) {

        Page<OrderStateHistoryEntity> paged = orderStatusService.getHistoryByFileIdPaged(fileId, PageRequest.of(page, size));
        if (paged == null || paged.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body("No history found for fileId: " + fileId);
        }
        return ResponseEntity.ok(paged);
    }

    /* -------------------------
       Endpoints for querying by currentState
       ------------------------- */

    /**
     * GET /api/orders/statuses/{state}
     * List all rows with the given currentState (descending by eventTime).
     */
    @GetMapping("/statuses/{state}")
    public ResponseEntity<?> getByCurrentState(@PathVariable("state") String state) {
        List<OrderStateHistoryEntity> list = orderStatusService.getByCurrentState(state);
        if (list == null || list.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body("No orders with state: " + state);
        }
        return ResponseEntity.ok(list);
    }

    /**
     * GET /api/orders/statuses/{state}/paged?page=0&size=20
     * Paged listing by currentState.
     */
    @GetMapping("/statuses/{state}/paged")
    public ResponseEntity<?> getByCurrentStatePaged(
            @PathVariable("state") String state,
            @RequestParam(name = "page", defaultValue = "0") int page,
            @RequestParam(name = "size", defaultValue = "20") int size) {

        Page<OrderStateHistoryEntity> paged = orderStatusService.getByCurrentStatePaged(state, PageRequest.of(page, size));
        if (paged == null || paged.isEmpty()) {
            return ResponseEntity.status(HttpStatus.NOT_FOUND).body("No orders with state: " + state);
        }
        return ResponseEntity.ok(paged);
    }

    /**
     * GET /api/orders/statuses/{state}/count
     * Returns count of rows with the given state.
     */
    @GetMapping("/statuses/{state}/count")
    public ResponseEntity<Long> countByState(@PathVariable("state") String state) {
        long count = orderStatusService.countByState(state);
        return ResponseEntity.ok(count);
    }

    /**
     * GET /api/orders/statuses/distinct
     * Returns list of distinct currentState values seen in the table.
     */
    @GetMapping("/statuses/distinct")
    public ResponseEntity<List<String>> distinctStatuses() {
        List<String> states = orderStatusService.getDistinctStates();
        return ResponseEntity.ok(states);
    }
}
