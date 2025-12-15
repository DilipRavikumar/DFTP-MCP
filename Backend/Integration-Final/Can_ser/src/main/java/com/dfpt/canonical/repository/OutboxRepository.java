package com.dfpt.canonical.repository;

import com.dfpt.canonical.model.OutboxEntity;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Repository
public interface OutboxRepository extends JpaRepository<OutboxEntity, UUID> {
    
    /**
     * Find all NEW events ready to be sent
     */
    @Query("SELECT o FROM OutboxEntity o WHERE o.status = 'NEW' ORDER BY o.createdAt ASC")
    List<OutboxEntity> findNewEvents();
    
    /**
     * Find failed events that can be retried
     */
    @Query("SELECT o FROM OutboxEntity o WHERE o.status = 'FAILED' AND o.retryCount < :maxRetries ORDER BY o.lastAttemptAt ASC")
    List<OutboxEntity> findRetryableEvents(@Param("maxRetries") int maxRetries);
    
    /**
     * Find events by status
     */
    List<OutboxEntity> findByStatus(String status);
    
    /**
     * Find events by aggregate ID
     */
    List<OutboxEntity> findByAggregateId(UUID aggregateId);
    
    /**
     * Find events created before a certain time (for cleanup)
     */
    @Query("SELECT o FROM OutboxEntity o WHERE o.status = 'SENT' AND o.createdAt < :cutoffTime")
    List<OutboxEntity> findCompletedEventsOlderThan(@Param("cutoffTime") LocalDateTime cutoffTime);
    
    /**
     * Update status for multiple events
     */
    @Modifying
    @Query("UPDATE OutboxEntity o SET o.status = :status, o.lastAttemptAt = :lastAttempt WHERE o.outboxId IN :ids")
    int updateStatus(@Param("ids") List<UUID> ids, @Param("status") String status, @Param("lastAttempt") LocalDateTime lastAttempt);
    
    /**
     * Increment retry count for failed events
     */
    @Modifying
    @Query("UPDATE OutboxEntity o SET o.retryCount = o.retryCount + 1, o.lastAttemptAt = :lastAttempt WHERE o.outboxId = :id")
    int incrementRetryCount(@Param("id") UUID id, @Param("lastAttempt") LocalDateTime lastAttempt);
}