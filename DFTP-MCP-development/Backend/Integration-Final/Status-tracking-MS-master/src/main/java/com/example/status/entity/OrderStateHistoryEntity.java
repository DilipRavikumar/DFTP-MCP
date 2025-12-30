package com.example.status.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Entity
@NoArgsConstructor
@AllArgsConstructor
@Table(name = "order_state_history")
public class OrderStateHistoryEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "file_id")
    private String fileId;

    @Column(name = "order_id")
    private String orderId;

    @Column(name = "distributor_id")
    private Integer distributorId;

    @Column(name = "previous_state")
    private String previousState;

    @Column(name = "current_state", nullable = false)
    private String currentState;

    @Column(name = "source_service")
    private String sourceService;

    @Column(name = "event_time", nullable = false)
    private LocalDateTime eventTime;
}