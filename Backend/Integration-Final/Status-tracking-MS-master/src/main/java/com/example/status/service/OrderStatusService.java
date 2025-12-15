package com.example.status.service;

import com.example.status.dao.OrderStateHistoryDao;
import com.example.status.entity.OrderStateHistoryEntity;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Service
public class OrderStatusService {

    private final OrderStateHistoryDao orderStateHistoryDao;

    public OrderStatusService(OrderStateHistoryDao orderStateHistoryDao) {
        this.orderStateHistoryDao = orderStateHistoryDao;
    }

    public Optional<OrderStateHistoryEntity> getLatestOrderStatus(String orderId) {
        return orderStateHistoryDao.findTopByOrderIdOrderByEventTimeDesc(orderId);
    }

    public Optional<OrderStateHistoryEntity> getLatestByFileId(String fileId) {
        if (fileId == null) return Optional.empty();
        return orderStateHistoryDao.findTopByFileIdOrderByEventTimeDesc(fileId);
    }


    public boolean fileExists(String fileId) {
        if (fileId == null) return false;
        return orderStateHistoryDao.existsByFileId(fileId);
    }

    public List<OrderStateHistoryEntity> getHistoryByFileId(String fileId) {
        if (fileId == null) return List.of();
        return orderStateHistoryDao.findByFileIdOrderByEventTimeDesc(fileId);
    }

    public Page<OrderStateHistoryEntity> getHistoryByFileIdPaged(String fileId, Pageable pageable) {
        if (fileId == null) return Page.empty();
        return orderStateHistoryDao.findByFileId(fileId, pageable);
    }

   public List<OrderStateHistoryEntity> getByCurrentState(String currentState) {
        if (currentState == null) return List.of();
        return orderStateHistoryDao.findByCurrentStateOrderByEventTimeDesc(currentState);
    } 

     public Page<OrderStateHistoryEntity> getByCurrentStatePaged(String currentState, Pageable pageable) {
        if (currentState == null) return Page.empty();
        return orderStateHistoryDao.findByCurrentState(currentState, pageable);
    }


    public long countByState(String currentState) {
        if (currentState == null) return 0L;
        return orderStateHistoryDao.countByCurrentState(currentState);
    }

    public List<String> getDistinctStates() {
        return orderStateHistoryDao.findDistinctCurrentStates();
    }

}
