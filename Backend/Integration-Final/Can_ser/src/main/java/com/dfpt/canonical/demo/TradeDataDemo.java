package com.dfpt.canonical.demo;

import com.dfpt.canonical.dto.ExternalTradeDTO;
import com.dfpt.canonical.model.CanonicalTrade;
import com.dfpt.canonical.service.TradeProcessingService;
import com.dfpt.canonical.service.FixedWidthParserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

/**
 * Demo class to show what data the TradeProcessingService receives
 */
@Component
public class TradeDataDemo {

    @Autowired
    private TradeProcessingService tradeProcessingService;

    @Autowired
    private FixedWidthParserService fixedWidthParserService;

    public void demonstrateInputDataFormats() {
        System.out.println("=".repeat(80));
        System.out.println("TRADE PROCESSING SERVICE - INPUT DATA DEMONSTRATION");
        System.out.println("=".repeat(80));

        // 1. JSON Format Example
        demonstrateJsonFormat();
        
        // 2. CSV Format Example  
        demonstrateCsvFormat();
        
        // 3. XML Format Example
        demonstrateXmlFormat();
        
        // 4. Fixed-Width Text Format Example
        demonstrateFixedWidthFormat();
        
        // 5. NIO Channel Processing Example
        demonstrateNioChannelFormat();
    }

    private void demonstrateJsonFormat() {
        System.out.println("\n1. JSON FORMAT INPUT:");
        System.out.println("-".repeat(40));
        
        String jsonExample = """
        {
          "trades": [
            {
              "originatorType": "1",
              "firmNumber": 1,
              "fundNumber": 1,
              "transactionType": "B",
              "transactionId": "TXN0000000000001",
              "tradeDateTime": "01012025093000",
              "dollarAmount": 150.00,
              "clientName": "JOHN DOE",
              "ssn": "123456789",
              "dob": "01011990",
              "shareQuantity": 250.00
            }
          ]
        }
        """;
        
        System.out.println("Raw JSON Input:");
        System.out.println(jsonExample);
        
        ExternalTradeDTO dto = new ExternalTradeDTO();
        dto.setOriginatorType("1");
        dto.setFirmNumber(1);
        dto.setFundNumber(1);
        dto.setTransactionType("B");
        dto.setTransactionId("TXN0000000000001");
        dto.setTradeDateTime("01012025093000");
        dto.setDollarAmount(new BigDecimal("150.00"));
        dto.setClientName("JOHN DOE");
        dto.setSsn("123456789");
        dto.setDob("01011990");
        dto.setShareQuantity(new BigDecimal("250.00"));
        
        System.out.println("\nParsed ExternalTradeDTO object:");
        printExternalTradeDTO(dto);
    }

    private void demonstrateCsvFormat() {
        System.out.println("\n2. CSV FORMAT INPUT:");
        System.out.println("-".repeat(40));
        
        String csvExample = """
        originatorType,firmNumber,fundNumber,transactionType,transactionId,tradeDateTime,dollarAmount,clientName,ssn,dob,shareQuantity
        1,1,1,B,TXN0000000000001,01012025093000,150.00,JOHN DOE,123456789,01011990,250.00
        0,2,2,S,TXN0000000000002,02012025101500,0.00,JANE SMITH,987654321,15071985,150.00
        """;
        
        System.out.println("Raw CSV Input:");
        System.out.println(csvExample);
        
        ExternalTradeDTO dto = new ExternalTradeDTO();
        dto.setOriginatorType("1");
        dto.setFirmNumber(1);
        dto.setFundNumber(1);
        dto.setTransactionType("B");
        dto.setTransactionId("TXN0000000000001");
        dto.setTradeDateTime("01012025093000");
        dto.setDollarAmount(new BigDecimal("150.00"));
        dto.setClientName("JOHN DOE");
        dto.setSsn("123456789");
        dto.setDob("01011990");
        dto.setShareQuantity(new BigDecimal("250.00"));
        
        System.out.println("\nParsed ExternalTradeDTO object:");
        printExternalTradeDTO(dto);
    }

    private void demonstrateXmlFormat() {
        System.out.println("\n3. XML FORMAT INPUT:");
        System.out.println("-".repeat(40));
        
        String xmlExample = """
        <?xml version="1.0" encoding="UTF-8"?>
        <Order>
            <OriginatorType>1</OriginatorType>
            <FirmNumber>1</FirmNumber>
            <FundNumber>1</FundNumber>
            <TransactionType>B</TransactionType>
            <TransactionId>TXN0000000000001</TransactionId>
            <TradeDateTime>01012025093000</TradeDateTime>
            <DollarAmount>150.00</DollarAmount>
            <ClientName>JOHN DOE</ClientName>
            <SSN>123456789</SSN>
            <DOB>01011990</DOB>
            <ShareQuantity>250.00</ShareQuantity>
        </Order>
        """;
        
        System.out.println("Raw XML Input:");
        System.out.println(xmlExample);
        
        ExternalTradeDTO dto = new ExternalTradeDTO();
        dto.setOriginatorType("1");
        dto.setFirmNumber(1);
        dto.setFundNumber(1);
        dto.setTransactionType("B");
        dto.setTransactionId("TXN0000000000001");
        dto.setTradeDateTime("01012025093000");
        dto.setDollarAmount(new BigDecimal("150.00"));
        dto.setClientName("JOHN DOE");
        dto.setSsn("123456789");
        dto.setDob("01011990");
        dto.setShareQuantity(new BigDecimal("250.00"));
        
        System.out.println("\nParsed ExternalTradeDTO object:");
        printExternalTradeDTO(dto);
    }

    private void demonstrateFixedWidthFormat() {
        System.out.println("\n4. FIXED-WIDTH TEXT FORMAT INPUT:");
        System.out.println("-".repeat(40));
        
        String fixedWidthExample = "000010001BTXN0000000000001210120251115000000000000100000ACCT0000000000000001RAHUL K             ABCDE1234F01011990                |";
        
        System.out.println("Raw Fixed-Width Input:");
        System.out.println("Line length: " + fixedWidthExample.length());
        System.out.println(fixedWidthExample);
        
        System.out.println("\nField positions breakdown:");
        System.out.println("Position 1-1    (OriginatorType): '" + fixedWidthExample.substring(0, 1) + "'");
        System.out.println("Position 2-5    (FirmNumber):     '" + fixedWidthExample.substring(1, 5) + "'");
        System.out.println("Position 6-9    (FundNumber):     '" + fixedWidthExample.substring(5, 9) + "'");
        System.out.println("Position 10-10  (TransactionType): '" + fixedWidthExample.substring(9, 10) + "'");
        System.out.println("Position 11-26  (TransactionId):  '" + fixedWidthExample.substring(10, 26) + "'");
        System.out.println("Position 27-40  (TradeDateTime):  '" + fixedWidthExample.substring(26, 40) + "'");
        System.out.println("Position 41-56  (DollarAmount):   '" + fixedWidthExample.substring(40, 56) + "'");
        System.out.println("Position 57-76  (ClientAccountNo): '" + fixedWidthExample.substring(56, 76) + "'");
        System.out.println("Position 77-96  (ClientName):     '" + fixedWidthExample.substring(76, 96) + "'");
        System.out.println("Position 97-105 (SSN):            '" + fixedWidthExample.substring(96, 105) + "'");
        System.out.println("Position 106-113 (DOB):           '" + fixedWidthExample.substring(105, 113) + "'");
        System.out.println("Position 114-129 (ShareQuantity): '" + fixedWidthExample.substring(113, 129) + "'");
        
        // Parse using FixedWidthParserService
        CanonicalTrade canonicalTrade = fixedWidthParserService.parseLineToCanonical(fixedWidthExample);
        
        System.out.println("\nParsed CanonicalTrade object:");
        printCanonicalTrade(canonicalTrade);
    }

    private void demonstrateNioChannelFormat() {
        System.out.println("\n5. NIO CHANNEL PROCESSING:");
        System.out.println("-".repeat(40));
        
        System.out.println("NIO Channel processing handles fixed-width format through ReadableByteChannel");
        System.out.println("- Processes data in 8192 byte buffers");
        System.out.println("- Expects fixed-width lines of at least 130 characters");
        System.out.println("- Each trade gets assigned a fileId and orderSource");
        System.out.println("- Used for high-performance streaming data processing");
        
        CanonicalTrade sampleTrade = new CanonicalTrade();
        sampleTrade.setFileId(UUID.randomUUID());
        sampleTrade.setOrderSource("NIO_STREAM");
        sampleTrade.setOriginatorType(1);
        sampleTrade.setFirmNumber(1);
        sampleTrade.setFundNumber(1);
        sampleTrade.setTransactionType("B");
        sampleTrade.setTransactionId("TXN0000000000001");
        sampleTrade.setDollarAmount(new BigDecimal("150.00"));
        sampleTrade.setClientName("JOHN DOE");
        sampleTrade.setSsn("123456789");
        sampleTrade.setShareQuantity(new BigDecimal("250.00"));
        sampleTrade.setStatus("RECEIVED");
        sampleTrade.setCreatedAt(LocalDateTime.now());
        
        System.out.println("\nSample CanonicalTrade from NIO processing:");
        printCanonicalTrade(sampleTrade);
    }

    private void printExternalTradeDTO(ExternalTradeDTO dto) {
        System.out.println("  OriginatorType: " + dto.getOriginatorType());
        System.out.println("  FirmNumber: " + dto.getFirmNumber());
        System.out.println("  FundNumber: " + dto.getFundNumber());
        System.out.println("  TransactionType: " + dto.getTransactionType());
        System.out.println("  TransactionId: " + dto.getTransactionId());
        System.out.println("  TradeDateTime: " + dto.getTradeDateTime());
        System.out.println("  DollarAmount: " + dto.getDollarAmount());
        System.out.println("  ClientAccountNo: " + dto.getClientAccountNo());
        System.out.println("  ClientName: " + dto.getClientName());
        System.out.println("  SSN: " + dto.getSsn());
        System.out.println("  DOB: " + dto.getDob());
        System.out.println("  ShareQuantity: " + dto.getShareQuantity());
    }

    private void printCanonicalTrade(CanonicalTrade trade) {
        System.out.println("  FileId: " + trade.getFileId());
        System.out.println("  RawOrderId: " + trade.getRawOrderId());
        System.out.println("  OrderSource: " + trade.getOrderSource());
        System.out.println("  OriginatorType: " + trade.getOriginatorType());
        System.out.println("  FirmNumber: " + trade.getFirmNumber());
        System.out.println("  FundNumber: " + trade.getFundNumber());
        System.out.println("  TransactionType: " + trade.getTransactionType());
        System.out.println("  TransactionId: " + trade.getTransactionId());
        System.out.println("  TradeDateTime: " + trade.getTradeDateTime());
        System.out.println("  DollarAmount: " + trade.getDollarAmount());
        System.out.println("  ClientAccountNo: " + trade.getClientAccountNo());
        System.out.println("  ClientName: " + trade.getClientName());
        System.out.println("  SSN: " + trade.getSsn());
        System.out.println("  DOB: " + trade.getDob());
        System.out.println("  ShareQuantity: " + trade.getShareQuantity());
        System.out.println("  Status: " + trade.getStatus());
        System.out.println("  CreatedAt: " + trade.getCreatedAt());
        System.out.println("  ValidatedAt: " + trade.getValidatedAt());
        System.out.println("  ValidationErrors: " + trade.getValidationErrors());
    }
}