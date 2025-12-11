package com.dfpt.canonical.repository;
import com.dfpt.canonical.model.Fund;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;
@Repository
public interface FundRepository extends JpaRepository<Fund, Integer> {
    Optional<Fund> findBySchemeCode(String schemeCode);
    List<Fund> findByStatus(String status);
}
