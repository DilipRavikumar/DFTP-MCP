package com.dfpt.canonical.service;
import com.dfpt.canonical.dto.ClientDTO;
import com.dfpt.canonical.dto.FundDTO;
import com.dfpt.canonical.dto.ValidationResult;
import com.dfpt.canonical.model.CanonicalTrade;
import com.dfpt.canonical.model.Client;
import com.dfpt.canonical.model.Fund;
import com.dfpt.canonical.repository.CanonicalTradeRepository;
import com.dfpt.canonical.repository.ClientRepository;
import com.dfpt.canonical.repository.FundRepository;
import org.kie.api.runtime.KieContainer;
import org.kie.api.runtime.KieSession;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.time.LocalTime;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;
@Service
public class ValidationService {
    private static final Logger logger = LoggerFactory.getLogger(ValidationService.class);
    @Autowired
    private RuleEngineService ruleEngineService;
    @Autowired
    private CanonicalTradeRepository canonicalTradeRepository;
    private final KieContainer kieContainer;
    private final String navCutoffTime;
    private final Double minimumInvestmentAmount;
    private final FundRepository fundRepository;
    private final ClientRepository clientRepository;
    public ValidationService(KieContainer kieContainer,
                             @Value("${validation.nav.cutoff:15:00}") String navCutoffTime,
                             @Value("${validation.minimum.amount:1000}") Double minimumInvestmentAmount,
                             FundRepository fundRepository,
                             ClientRepository clientRepository,
                             CanonicalTradeRepository canonicalTradeRepository) {
        this.kieContainer = kieContainer;
        this.navCutoffTime = navCutoffTime;
        this.minimumInvestmentAmount = minimumInvestmentAmount;
        this.fundRepository = fundRepository;
        this.clientRepository = clientRepository;
        this.canonicalTradeRepository = canonicalTradeRepository;
    }
    public ValidationResult validate(CanonicalTrade data) {
        KieSession kieSession = null;
        try {
            System.out.println("\n" + "==".repeat(50));
            System.out.println("📥 CANONICAL TO VALIDATION - INPUT DATA");
            System.out.println("==".repeat(50));
            System.out.println(formatCanonicalTradeForLog(data));
            System.out.println("==".repeat(50));
            
            logger.info("========== VALIDATION INPUT ==========");
            logger.info("CanonicalTrade: {}", formatCanonicalTradeForLog(data));
            logger.info("======================================");
            kieSession = kieContainer.newKieSession();
            ValidationResult result = new ValidationResult();
            kieSession.insert(data);
            kieSession.insert(result);
            kieSession.setGlobal("ruleEngineService", ruleEngineService);
            kieSession.setGlobal("navCutoffTime", LocalTime.parse(navCutoffTime));
            kieSession.setGlobal("minimumInvestmentAmount", minimumInvestmentAmount);
            kieSession.setGlobal("requestId", UUID.randomUUID().toString());
            List<Fund> funds = fundRepository.findAll();
            for (Fund f : funds) {
                FundDTO fundDto = new FundDTO();
                fundDto.setFundId(f.getFundId());
                fundDto.setSchemeCode(f.getSchemeCode());
                fundDto.setStatus(f.getStatus());
                fundDto.setMinLimit(f.getMinLimit());
                fundDto.setMaxLimit(f.getMaxLimit());
                kieSession.insert(fundDto);
            }
            List<Client> clients = clientRepository.findAll();
            for (Client c : clients) {
                ClientDTO clientDto = new ClientDTO();
                clientDto.setClientId(c.getClientId());
                clientDto.setKycStatus(c.getKycStatus());
                clientDto.setPanNumber(c.getPanNumber());
                clientDto.setStatus(c.getStatus());
                clientDto.setType(c.getType());
                kieSession.insert(clientDto);
            }
            int rulesFired = kieSession.fireAllRules();
            System.out.println("\n" + "==".repeat(50));
            System.out.println("📤 VALIDATION OUTPUT - RESULT DATA");
            System.out.println("==".repeat(50));
            System.out.printf("Rules Fired: %d%n", rulesFired);
            System.out.println(formatValidationResultForLog(result));
            System.out.println("==".repeat(50) + "\n");
            
            logger.info("========== VALIDATION OUTPUT ==========");
            logger.info("Rules Fired: {}", rulesFired);
            logger.info("ValidationResult: {}", formatValidationResultForLog(result));
            logger.info("=======================================");
            return result;
        } catch (Exception e) {
            logger.error("Error during Drools validation", e);
            ValidationResult errorResult = new ValidationResult();
            errorResult.addError("Validation engine error: " + e.getMessage());
            return errorResult;
        } finally {
            if (kieSession != null) {
                kieSession.dispose();
            }
        }
    }
    public List<ValidationResult> validateBatch(List<CanonicalTrade> trades) {
        KieSession kieSession = null;
        try {
            kieSession = kieContainer.newKieSession();
            kieSession.setGlobal("ruleEngineService", ruleEngineService);
            kieSession.setGlobal("navCutoffTime", LocalTime.parse(navCutoffTime));
            kieSession.setGlobal("minimumInvestmentAmount", minimumInvestmentAmount);
            kieSession.setGlobal("requestId", UUID.randomUUID().toString());
            List<Fund> funds = fundRepository.findAll();
            List<Client> clients = clientRepository.findAll();
            logger.info("Loaded {} clients and {} funds for batch validation of {} trades", 
                clients.size(), funds.size(), trades.size());
            for (Fund f : funds) {
                FundDTO fundDto = new FundDTO();
                fundDto.setFundId(f.getFundId());
                fundDto.setSchemeCode(f.getSchemeCode());
                fundDto.setStatus(f.getStatus());
                fundDto.setMinLimit(f.getMinLimit());
                fundDto.setMaxLimit(f.getMaxLimit());
                kieSession.insert(fundDto);
            }
            for (Client c : clients) {
                ClientDTO clientDto = new ClientDTO();
                clientDto.setClientId(c.getClientId());
                clientDto.setKycStatus(c.getKycStatus());
                clientDto.setPanNumber(c.getPanNumber());
                clientDto.setStatus(c.getStatus());
                clientDto.setType(c.getType());
                kieSession.insert(clientDto);
            }
            List<ValidationResult> results = new java.util.ArrayList<>();
            for (CanonicalTrade trade : trades) {
                ValidationResult result = new ValidationResult();
                kieSession.insert(trade);
                kieSession.insert(result);
                results.add(result);
            }
            int rulesFired = kieSession.fireAllRules();
            logger.info("Batch validation completed - {} rules fired for {} trades", rulesFired, trades.size());
            return results;
        } catch (Exception e) {
            logger.error("Error during batch Drools validation", e);
            List<ValidationResult> errorResults = new java.util.ArrayList<>();
            for (CanonicalTrade trade : trades) {
                ValidationResult errorResult = new ValidationResult();
                errorResult.addError("Validation engine error: " + e.getMessage());
                errorResults.add(errorResult);
            }
            return errorResults;
        } finally {
            if (kieSession != null) {
                kieSession.dispose();
            }
        }
    }
    @Transactional
    public void storeValidOrders(CanonicalTrade trade) {
        CanonicalTrade savedTrade = canonicalTradeRepository.save(trade);
        logger.debug("Stored trade with ID: {}", savedTrade.getId());
    }
    @Transactional
    public void storeValidOrdersBatch(List<CanonicalTrade> trades) {
        List<CanonicalTrade> savedTrades = canonicalTradeRepository.saveAll(trades);
        logger.info("Stored {} trades in batch", savedTrades.size());
    }
    private String formatCanonicalTradeForLog(CanonicalTrade ct) {
        if (ct == null) return "❌ NULL TRADE DATA";
        return String.format(
            "📋 CANONICAL TRADE DETAILS:" +
            "\n  🆔 Transaction ID: %s" +
            "\n  🔄 Transaction Type: %s" +
            "\n  🏢 Originator Type: %s" +
            "\n  🏪 Firm Number: %s" +
            "\n  💰 Fund Number: %s" +
            "\n  👤 Client Name: %s" +
            "\n  🔐 SSN: %s" +
            "\n  📅 DOB: %s" +
            "\n  ⏰ Trade DateTime: %s" +
            "\n  💵 Dollar Amount: %s" +
            "\n  📊 Share Quantity: %s" +
            "\n  🏦 Client Account No: %s" +
            "\n  📝 Status: %s" +
            "\n  📄 File ID: %s" +
            "\n  📤 Order Source: %s",
            ct.getTransactionId(),
            ct.getTransactionType(),
            ct.getOriginatorType(),
            ct.getFirmNumber(),
            ct.getFundNumber(),
            ct.getClientName(),
            ct.getSsn(),
            ct.getDob(),
            ct.getTradeDateTime(),
            ct.getDollarAmount(),
            ct.getShareQuantity(),
            ct.getClientAccountNo(),
            ct.getStatus(),
            ct.getFileId(),
            ct.getOrderSource()
        );
    }
    private String formatValidationResultForLog(ValidationResult vr) {
        if (vr == null) return "❌ NULL VALIDATION RESULT";
        List<String> errors = vr.getErrors();
        boolean isValid = (errors == null || errors.isEmpty());
        String status = isValid ? "✅ VALIDATION PASSED" : "❌ VALIDATION FAILED";
        String errorDetails = "";
        
        if (!isValid) {
            errorDetails = "\n  🚫 Error Count: " + errors.size() + "\n  📋 Error Details:";
            for (int i = 0; i < errors.size(); i++) {
                errorDetails += String.format("\n    %d. %s", i + 1, errors.get(i));
            }
        } else {
            errorDetails = "\n  🎉 No validation errors found!";
        }
        
        return String.format("📊 VALIDATION RESULT:\n  %s%s", status, errorDetails);
    }
}
