package com.dftp.Entity;

import java.time.Instant;
import java.util.UUID;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "raw_orders")
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RawOrderEntity {

    @Id
    private UUID id;

    private String source;

    @Column(columnDefinition = "TEXT")
    private String payload;


    private byte[] fileBytes;

    private String payloadType;

    private String filename;
    private Long fileSize;

    private String checksum;

    private Instant receivedAt;
}

