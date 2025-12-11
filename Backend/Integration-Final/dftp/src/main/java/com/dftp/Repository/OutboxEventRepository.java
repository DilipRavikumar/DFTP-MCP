
package com.dftp.Repository;

import java.util.List;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.dftp.Entity.OutboxEventEntity;

public interface OutboxEventRepository extends JpaRepository<OutboxEventEntity, UUID> {

    List<OutboxEventEntity> findByStatus(String status);
    
    List<OutboxEventEntity> findByRawOrderId(UUID rawOrderId);
}
