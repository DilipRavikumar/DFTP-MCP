package com.example.demo.Simulator.Service;

import org.springframework.stereotype.Service;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

@Service
public class OrderGenerator {

    private final Random random = new Random();
    private final String[] names = { "RAHUL K", "PRIYA S", "AMIT P", "NEHA M", "RAVI T", "SITA D", "KIRAN J",
            "MAYA R" };
    private final String dummyData = "SOURCEPLATFORMBATCH20250130PROCESSORDERLOADSTATUSPENDINGCHECKSUM7C4A8D09TRADEDETAILSEXECUTIONVENUENYSEORDERTYPEMARKETLIMITPRICEVALIDATIONPASSEDRISKASSESSMENTLOWCLEARINGSETTLEMENTPENDINGCUSTODIANSERVICEACTIVECOUNTERPARTYBANKOFAMERICAREGULATORYSECCOMPLIANCEAPPROVEDAUDITTRAILCREATEDTIMESTAMP20250130111500BROKERCOMMISSION250TAXESCALCULATED150NETAMOUNT499600CURRENCYUSDEXCHANGERATENAPPLICABLEPORTFOLIOIDPF001STRATEGYGROWTHBENCHMARKSP500PERFORMANCEMETRICSTRACKINGACTIVEMANAGEMENTFEEANNUAL075EXPENSERATIOTOTAL125DIVIDENDPOLICYQUARTERLYREINVESTMENTAUTOMATICREBALANCINGMONTHLYRISKTOLERANCE ADDITIONALDATAPADDING";

    public List<String> generateRandomOrders(int count) {
        List<String> orders = new ArrayList<>();

        for (int i = 0; i < count; i++) {
            StringBuilder order = new StringBuilder();

            // Pos 1: Retail originator
            order.append("0");
            
            // Pos 2-5: Firm number
            order.append(String.format("%04d", random.nextInt(20) + 1));
            
            // Pos 6-9: Fund number
            order.append(String.format("%04d", random.nextInt(20) + 1));
            
            // Pos 10: Buy/Sell transaction
            order.append(random.nextBoolean() ? "B" : "S");
            
            // Pos 11-26: Transaction ID
            order.append(String.format("TXN%013d", Math.abs(random.nextLong()) % 1000000000000L));

            // Pos 27-40: Date/Time (ddMMyyyyHHmmss)
            LocalDateTime now = LocalDateTime.now();
            order.append(now.format(DateTimeFormatter.ofPattern("ddMMyyyyHHmmss")));

            // Pos 41-56: Amount (16 digits)
            long amount = random.nextInt(999999) + 10000;
            order.append(String.format("%016d", amount));
            
            // Pos 57-76: Account number
            order.append(String.format("ACCT%016d", Math.abs(random.nextLong()) % 10000000000000000L));

            // Pos 77-96: Client name (20 chars with spaces)
            String name = names[random.nextInt(names.length)];
            order.append(String.format("%-20s", name));
            
            // Pos 97-105: SSN/PAN (9 chars)
            order.append(String.format("%09d", random.nextInt(999999999)));

            // Pos 106-113: DOB (ddMMyyyy)
            int year = 1970 + random.nextInt(35);
            int month = 1 + random.nextInt(12);
            int day = 1 + random.nextInt(28);
            order.append(String.format("%02d%02d%d", day, month, year));

            // Pos 114-129: Spaces (16 chars)
            order.append("                ");

            // Pos 130-765: Dummy trade data (636 chars)
            StringBuilder dummy = new StringBuilder();
            while (dummy.length() < 636) {
                dummy.append(dummyData);
            }
            order.append(dummy.substring(0, 636));
            
            // Pos 766: Delimiter
            order.append("|");

            orders.add(order.toString());
        }

        return orders;
    }
}