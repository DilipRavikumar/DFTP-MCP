package com.dfpt.canonical.service;
import com.dfpt.canonical.model.CanonicalTrade;
import com.dfpt.canonical.dto.ValidationResult;
import com.dfpt.canonical.dto.FundDTO;
import com.dfpt.canonical.dto.ClientDTO;
import org.springframework.stereotype.Service;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.LocalTime;
@Service
public class RuleEngineService {
    private boolean addError(ValidationResult res, String error) {
        if (res == null) return false;
        String all = res.getErrors() == null ? "" : res.getErrors().toString();
        if (!all.contains(error)) {
            res.addError(error);
            return true;
        }
        return false;
    }
    public boolean handleMandatoryFields(CanonicalTrade ct, ValidationResult res) {
        if (ct == null || res == null) return false;
        boolean missing =
                ct.getOriginatorType() == null ||
                ct.getTransactionType() == null || ct.getTransactionType().trim().isEmpty() ||
                ct.getTransactionId() == null || ct.getTransactionId().trim().isEmpty() ||
                ct.getClientName() == null || ct.getClientName().trim().isEmpty() ||
                ct.getFirmNumber() == null ||
                ct.getFundNumber() == null ||
                ct.getClientAccountNo() == null ||
                ct.getTradeDateTime() == null ||
                ct.getDob() == null;
        if (missing) {
            return addError(res, "Mandatory fields missing or empty.");
        }
        return false;
    }
    public boolean handleCutoff(CanonicalTrade ct, ValidationResult res, LocalTime navCutoffTime) {
        if (ct == null || res == null) return false;
        LocalDateTime dt = ct.getTradeDateTime();
        LocalTime orderTime = (dt != null) ? dt.toLocalTime() : LocalTime.now();
        if (navCutoffTime != null && orderTime.isAfter(navCutoffTime)) {
            return addError(res, "Order received after NAV cut-off; will be processed for next day's NAV.");
        }
        return false;
    }
    public boolean handleUnknownClient(CanonicalTrade ct, ValidationResult res, ClientDTO client) {
        if (ct == null || res == null) return false;
        if (client == null) {
            return addError(res, "Unknown client.");
        }
        return false;
    }
    public boolean handleKyc(CanonicalTrade ct, ValidationResult res, ClientDTO client) {
        if (ct == null || res == null) return false;
        String kyc = client == null ? null : client.getKycStatus();
        if (kyc == null || !"YES".equalsIgnoreCase(kyc)) {
            return addError(res, "Investor KYC not valid for scheme (DB).");
        }
        return false;
    }
    public boolean handleUnknownFund(CanonicalTrade ct, ValidationResult res, FundDTO fund) {
        if (ct == null || res == null) return false;
        if (fund == null) {
            return addError(res, "Unknown scheme/fund.");
        }
        return false;
    }
    public boolean handleFundStatus(CanonicalTrade ct, ValidationResult res, FundDTO fund) {
        if (ct == null || res == null) return false;
        String status = fund == null ? null : fund.getStatus();
        if (status == null || !"ACTIVE".equalsIgnoreCase(status)) {
            return addError(res, "Scheme not open for transactions.");
        }
        return false;
    }
    public boolean handleFundLimits(CanonicalTrade ct, ValidationResult res, FundDTO fund) {
        if (ct == null || res == null) return false;
        if (fund == null) return addError(res, "Unknown scheme/fund."); // defensive
        BigDecimal min = fund.getMinLimit();
        BigDecimal max = fund.getMaxLimit();
        BigDecimal amt = toBigDecimal(ct.getDollarAmount());
        if (amt == null || (min != null && amt.compareTo(min) < 0) || (max != null && amt.compareTo(max) > 0)) {
            String minS = (min == null) ? "-inf" : min.toString();
            String maxS = (max == null) ? "+inf" : max.toString();
            return addError(res, "Order amount out of allowed scheme limits. (allowed: " + minS + " - " + maxS + ")");
        }
        return false;
    }
    public boolean handleClientStatus(CanonicalTrade ct, ValidationResult res, ClientDTO client) {
        if (ct == null || res == null) return false;
        String status = client == null ? null : client.getStatus();
        if (status == null || !"ACTIVE".equalsIgnoreCase(status)) {
            return addError(res, "Investor account not active.");
        }
        return false;
    }
    public boolean handleBuyOrder(CanonicalTrade ct, ValidationResult res) {
        if (ct == null || res == null) return false;
        boolean changed = false;
        boolean hasAmount = ct.getDollarAmount() != null;
        boolean hasQty = ct.getShareQuantity() != null;
        if (!hasAmount) changed |= addError(res, "BUY order requires amount.");
        if (hasQty) changed |= addError(res, "BUY order cannot have quantity.");
        return changed;
    }
    public boolean handleSellOrder(CanonicalTrade ct, ValidationResult res) {
        if (ct == null || res == null) return false;
        boolean changed = false;
        boolean hasAmount = ct.getDollarAmount() != null;
        boolean hasQty = ct.getShareQuantity() != null;
        if (!hasQty) changed |= addError(res, "SELL order requires quantity.");
        if (hasAmount) changed |= addError(res, "SELL order cannot have amount.");
        return changed;
    }
    public boolean handleSwitchOrder(CanonicalTrade ct, ValidationResult res) {
        if (ct == null || res == null) return false;
        boolean hasAmount = ct.getDollarAmount() != null;
        boolean hasQty = ct.getShareQuantity() != null;
        if (!hasAmount || !hasQty) {
            return addError(res, "SWITCH order requires BOTH amount and quantity.");
        }
        return false;
    }
    private BigDecimal toBigDecimal(Object obj) {
        if (obj == null) return null;
        if (obj instanceof BigDecimal) return (BigDecimal) obj;
        if (obj instanceof Number) {
            return BigDecimal.valueOf(((Number) obj).doubleValue());
        }
        try {
            return new BigDecimal(obj.toString());
        } catch (Exception e) {
            return null;
        }
    }
}
