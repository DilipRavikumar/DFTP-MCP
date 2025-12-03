package com.trade;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface FraudResultRepository extends JpaRepository<FraudResult, Long> {
}