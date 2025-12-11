
package com.dftp.Repository;

import java.util.Optional;
import java.util.UUID;

import org.springframework.data.jpa.repository.JpaRepository;

import com.dftp.Entity.RawOrderEntity;

public interface RawOrderRepository extends JpaRepository<RawOrderEntity, UUID> {
    Optional<RawOrderEntity> findByChecksum(String checksum);
}
