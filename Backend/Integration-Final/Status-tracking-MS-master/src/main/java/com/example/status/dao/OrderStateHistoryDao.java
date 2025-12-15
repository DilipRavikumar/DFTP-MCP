package com.example.status.dao;
import com.example.status.entity.OrderStateHistoryEntity;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.Optional;  

public interface OrderStateHistoryDao extends JpaRepository<OrderStateHistoryEntity, Long> {

    Optional<OrderStateHistoryEntity> findTopByFileIdAndOrderIdAndDistributorIdOrderByEventTimeDesc(
        String fileId,
        String orderId,
        Integer distributorId
    );


    Optional<OrderStateHistoryEntity> findTopByFileIdOrderByEventTimeDesc(String fileId);
    
    Optional<OrderStateHistoryEntity> findTopByOrderIdAndDistributorIdOrderByEventTimeDesc(
        String orderId,
        Integer distributorId
    );
    
    Optional<OrderStateHistoryEntity> findTopByOrderIdOrderByEventTimeDesc(String orderId);

    boolean existsByFileId(String fileId);

    // --- new methods for history listing ---
    List<OrderStateHistoryEntity> findByFileIdOrderByEventTimeDesc(String fileId);

    // pageable query (useful for large histories)
    Page<OrderStateHistoryEntity> findByFileId(String fileId, Pageable pageable);

    List<OrderStateHistoryEntity> findByCurrentStateOrderByEventTimeDesc(String currentState);

    Page<OrderStateHistoryEntity> findByCurrentState(String currentState, Pageable pageable);

    List<OrderStateHistoryEntity> findByCurrentStateAndSourceServiceOrderByEventTimeDesc(
        String currentState, String sourceService);

        @Query("select distinct o.currentState from OrderStateHistoryEntity o")
     List<String> findDistinctCurrentStates();

     long countByCurrentState(String currentState);
}   