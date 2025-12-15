package com.dfpt.canonical.repository;
import com.dfpt.canonical.model.Client;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;
@Repository
public interface ClientRepository extends JpaRepository<Client, Integer> {
    List<Client> findByKycStatus(String kycStatus);
    List<Client> findByStatus(String status);
    List<Client> findByKycStatusAndStatus(String kycStatus, String status);
}
