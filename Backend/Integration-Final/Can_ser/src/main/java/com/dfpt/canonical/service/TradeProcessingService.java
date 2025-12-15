// package com.dfpt.canonical.service;
// import com.dfpt.canonical.dto.ExternalTradeDTO;
// import com.dfpt.canonical.dto.ExternalTradeListDTO;
// import com.dfpt.canonical.dto.ProcessingResult;
// import com.dfpt.canonical.dto.ValidationResult;
// import com.dfpt.canonical.model.CanonicalTrade;
// import com.dfpt.canonical.repository.CanonicalTradeRepository;
// import com.fasterxml.jackson.databind.ObjectMapper;
// import com.fasterxml.jackson.dataformat.xml.XmlMapper;
// import com.opencsv.bean.CsvToBean;
// import com.opencsv.bean.CsvToBeanBuilder;
// import org.slf4j.Logger;
// import org.slf4j.LoggerFactory;
// import org.springframework.beans.factory.annotation.Autowired;
// import org.springframework.stereotype.Service;
// import java.io.BufferedReader;
// import java.io.File;
// import java.io.FileReader;
// import java.math.BigDecimal;
// import java.nio.ByteBuffer;
// import java.nio.channels.ReadableByteChannel;
// import java.time.LocalDate;
// import java.time.LocalDateTime;
// import java.time.format.DateTimeFormatter;
// import java.util.ArrayList;
// import java.util.Arrays;
// import java.util.List;
// import java.util.Collections;
// import java.util.UUID;
// @Service
// public class TradeProcessingService {
//     private static final Logger logger = LoggerFactory.getLogger(TradeProcessingService.class);
//     private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
//     private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd");
//     @Autowired
//     private CanonicalTradeRepository tradeRepository;
//     @Autowired
//     private FixedWidthParserService fixedWidthParserService;
//     @Autowired
//     private ValidationService validationService;
//     @Autowired
//     private StatusStreamPublisher statusPublisher;
    
//     public ProcessingResult processTradeFileFromChannel(ReadableByteChannel channel, String fileName, UUID fileId, String source) {
//         ProcessingResult result = new ProcessingResult();
//         result.setFileName(fileName);
//         try {
//             String format = getFileFormat(fileName);
//             result.setFormat(format);
//             if (!"txt".equalsIgnoreCase(format)) {
//                 result.setStatus("ERROR");
//                 result.addError("NIO channel processing only supports TXT (fixed-width) format");
//                 return result;
//             }
//             List<CanonicalTrade> trades = parseFixedWidthFromChannel(channel);
//             result.setTotalRecords(trades.size());
//             if (trades.isEmpty()) {
//                 result.setStatus("FAILED");
//                 result.addError("No records found");
//                 return result;
//             }
            
//             trades.forEach(trade -> {
//                 trade.setFileId(fileId);
//                 trade.setRawOrderId(UUID.randomUUID());
//                 trade.setOrderSource(source);
//             });
//             logger.info("Processing {} trades with fileId: {}, source: {}", trades.size(), fileId, source);
            
//             int successCount = 0;
//             int failedCount = 0;
//             logger.info("Starting validation for {} trades", trades.size());
//             long validationStart = System.currentTimeMillis();
            
//             // Print detailed information about received trade data
//             System.out.println("\n" + ">>".repeat(25));
//             System.out.println("🔄 CANONICAL SERVICE - SENDING TO VALIDATION (NIO Channel)");
//             System.out.println(">>".repeat(25));
//             System.out.printf("Total trades received: %d%n", trades.size());
            
//             logger.info("=== RECEIVED TRADE DATA DETAILS ===");
//             logger.info("Total trades received: {}", trades.size());
//             for (int i = 0; i < trades.size(); i++) {
//                 CanonicalTrade canonical = trades.get(i);
                
//                 System.out.printf("Trade #%d: TransactionId=%s, Type=%s, Amount=%s, Client=%s%n", 
//                     i + 1, canonical.getTransactionId(), canonical.getTransactionType(), 
//                     canonical.getDollarAmount(), canonical.getClientName());
//                 System.out.println(">>".repeat(25) + "\n");
                
//                 logger.info("Trade #{}: TransactionId={}, Type={}, Amount={}, Client={}, SSN={}, ShareQty={}, DateTime={}, FileId={}, Source={}", 
//                     i + 1, 
//                     canonical.getTransactionId(),
//                     canonical.getTransactionType(),
//                     canonical.getDollarAmount(),
//                     canonical.getClientName(),
//                     canonical.getSsn(),
//                     canonical.getClientAccountNo(),
//                     canonical.getShareQuantity(),
//                     canonical.getTradeDateTime(),
//                     canonical.getFileId(),
//                     canonical.getOrderSource());
//                 ValidationResult validationResult = validationService.validate(canonical);
//                 try {
//                     if (canonical.getClientAccountNo() == null) {
//                         canonical.setClientAccountNo(i + 1);
//                     }
//                     if (!validationResult.isValid() || !validationResult.getErrors().isEmpty()) {
//                         canonical.setStatus("VALIDATION_FAILED");
//                         canonical.setValidationErrors(String.join("; ", validationResult.getErrors()));
//                         result.addError("Trade " + (i + 1) + " validation failed: " + String.join("; ", validationResult.getErrors()));
//                         failedCount++;
//                     } else {
//                         canonical.setStatus("VALIDATED");
//                         successCount++;
//                     }
//                     canonical.setValidatedAt(LocalDateTime.now());
//                     CanonicalTrade saved = tradeRepository.save(canonical);
//                     result.addProcessedTrade(saved);
                    
//                     try {
//                         statusPublisher.publishTradeStatus(saved);
//                     } catch (Exception statusEx) {
//                         logger.warn("Failed to publish status for trade {}: {}", saved.getTransactionId(), statusEx.getMessage());
//                     }
//                 } catch (Exception e) {
//                     failedCount++;
//                     result.addError("Processing error for trade " + (i + 1) + ": " + e.getMessage());
//                     logger.error("Trade processing failed", e);
//                 }
//             }
//             long validationTime = System.currentTimeMillis() - validationStart;
//             logger.info("Validation completed in {} ms - Success: {}, Failed: {}", validationTime, successCount, failedCount);
//             result.setSuccessCount(successCount);
//             result.setFailedCount(failedCount);
//             if (failedCount == 0) {
//                 result.setStatus("SUCCESS");
//             } else if (successCount > 0) {
//                 result.setStatus("PARTIAL_SUCCESS");
//             } else {
//                 result.setStatus("FAILED");
//             }
            
//             try {
//                 statusPublisher.publishBatchStatus(fileName, trades.size(), successCount, failedCount);
//             } catch (Exception statusEx) {
//                 logger.warn("Failed to publish batch status for file {}: {}", fileName, statusEx.getMessage());
//             }
            
//             logger.info("NIO Channel processing completed: {}", result);
//         } catch (Exception e) {
//             result.setStatus("ERROR");
//             result.addError("Channel processing error: " + e.getMessage());
//             logger.error("Error processing from channel: {}", fileName, e);
//         }
//         return result;
//     }
//     private List<CanonicalTrade> parseFixedWidthFromChannel(ReadableByteChannel channel) throws Exception {
//         List<CanonicalTrade> trades = new ArrayList<>();
//         ByteBuffer buffer = ByteBuffer.allocate(8192);
//         StringBuilder lineBuilder = new StringBuilder();
//         while (channel.read(buffer) != -1) {
//             buffer.flip();
//             while (buffer.hasRemaining()) {
//                 char c = (char) buffer.get();
//                 if (c == '\n') {
//                     String line = lineBuilder.toString().trim();
//                     if (!line.isEmpty() && line.length() >= 130) {
//                         try {
//                             logger.debug("Parsing fixed-width line: {}", line);
//                             CanonicalTrade trade = fixedWidthParserService.parseLineToCanonical(line);
//                             if (trade != null) {
//                                 trades.add(trade);
//                                 logger.debug("Successfully parsed trade: TransactionId={}, Type={}, Amount={}", 
//                                     trade.getTransactionId(), trade.getTransactionType(), trade.getDollarAmount());
//                             }
//                         } catch (Exception e) {
//                             logger.warn("Failed to parse line: {}", line, e);
//                         }
//                     }
//                     lineBuilder.setLength(0);
//                 } else if (c != '\r') {
//                     lineBuilder.append(c);
//                 }
//             }
//             buffer.clear();
//         }
//         if (lineBuilder.length() > 0) {
//             String line = lineBuilder.toString().trim();
//             if (!line.isEmpty() && line.length() >= 130) {
//                 try {
//                     CanonicalTrade trade = fixedWidthParserService.parseLineToCanonical(line);
//                     if (trade != null) {
//                         trades.add(trade);
//                     }
//                 } catch (Exception e) {
//                     logger.warn("Failed to parse final line: {}", line, e);
//                 }
//             }
//         }
//         logger.info("Parsed {} trades from NIO channel", trades.size());
//         return trades;
//     }
//     public ProcessingResult processTradeFile(String fileName) {
//         ProcessingResult result = new ProcessingResult();
//         result.setFileName(fileName);
//         try {
//             String format = getFileFormat(fileName);
//             result.setFormat(format);
//             File file = new File(fileName);
//             List<ExternalTradeDTO> trades = parseFile(file, format);
//             result.setTotalRecords(trades.size());
//             if (trades.isEmpty()) {
//                 result.setStatus("FAILED");
//                 result.addError("No records found");
//                 return result;
//             }
//             int successCount = 0;
//             int failedCount = 0;
            
//             // Print detailed information about received external trade data
//             logger.info("=== RECEIVED EXTERNAL TRADE DATA DETAILS ===");
//             logger.info("File format: {}, Total trades received: {}", format, trades.size());
//             for (int i = 0; i < trades.size(); i++) {
//                 ExternalTradeDTO trade = trades.get(i);
//                 logger.info("External Trade #{}: OriginatorType={}, FirmNo={}, FundNo={}, TxnType={}, TxnId={}, DateTime={}, Amount={}, ClientName={}, SSN={}, DOB={}, ShareQty={}", 
//                     i + 1,
//                     trade.getOriginatorType(),
//                     trade.getFirmNumber(),
//                     trade.getFundNumber(),
//                     trade.getTransactionType(),
//                     trade.getTransactionId(),
//                     trade.getTradeDateTime(),
//                     trade.getDollarAmount(),
//                     trade.getClientName(),
//                     trade.getSsn(),
//                     trade.getDob(),
//                     trade.getShareQuantity());
//                 try {
//                     if (trade.getClientAccountNo() == null) {
//                         trade.setClientAccountNo(i + 1);
//                     }
//                     CanonicalTrade canonical = convertToCanonicalTrade(trade);
                    
//                     System.out.println("\n" + ">>".repeat(25));
//                     System.out.println("🔄 CANONICAL SERVICE - SENDING TO VALIDATION");
//                     System.out.println(">>".repeat(25));
//                     System.out.printf("Converting External Trade #%d to Canonical Trade%n", i + 1);
//                     System.out.printf("🆔 Transaction ID: %s%n", canonical.getTransactionId());
//                     System.out.printf("🔄 Transaction Type: %s%n", canonical.getTransactionType());
//                     System.out.printf("💵 Dollar Amount: %s%n", canonical.getDollarAmount());
//                     System.out.printf("👤 Client Name: %s%n", canonical.getClientName());
//                     System.out.printf("🔐 SSN: %s%n", canonical.getSsn());
//                     System.out.printf("📊 Share Quantity: %s%n", canonical.getShareQuantity());
//                     System.out.printf("⏰ Trade DateTime: %s%n", canonical.getTradeDateTime());
//                     System.out.println(">>".repeat(25) + "\n");
                    
//                     logger.info("=== SENDING TO VALIDATION ===");
//                     logger.info("Converting External Trade #{} to Canonical Trade:", i + 1);
//                     logger.info("Canonical Trade Data: TransactionId={}, Type={}, Amount={}, Client={}, SSN={}, ShareQty={}, DateTime={}",
//                         canonical.getTransactionId(),
//                         canonical.getTransactionType(),
//                         canonical.getDollarAmount(),
//                         canonical.getClientName(),
//                         canonical.getSsn(),
//                         canonical.getShareQuantity(),
//                         canonical.getTradeDateTime());
                    
//                     ValidationResult validationResult = validationService.validate(canonical);
                    
//                     if (!validationResult.isValid() || !validationResult.getErrors().isEmpty()) {
//                         canonical.setStatus("VALIDATION_FAILED");
//                         canonical.setValidationErrors(String.join("; ", validationResult.getErrors()));
//                         result.addError("Trade " + (i + 1) + " validation failed: " + String.join("; ", validationResult.getErrors()));
//                         failedCount++;
//                         logger.warn("Trade #{} validation FAILED: {}", i + 1, validationResult.getErrors());
//                     } else {
//                         canonical.setStatus("VALIDATED");
//                         successCount++;
//                         logger.info("Trade #{} validation PASSED", i + 1);
//                     }
//                     canonical.setValidatedAt(LocalDateTime.now());
//                     CanonicalTrade saved = tradeRepository.save(canonical);
//                     result.addProcessedTrade(saved);
                    
//                     try {
//                         statusPublisher.publishTradeStatus(saved);
//                     } catch (Exception statusEx) {
//                         logger.warn("Failed to publish status for trade {}: {}", saved.getTransactionId(), statusEx.getMessage());
//                     }
//                 } catch (Exception e) {
//                     failedCount++;
//                     result.addError("Processing error for trade " + (i + 1) + ": " + e.getMessage());
//                     logger.error("Trade #{} processing failed", i + 1, e);
//                 }
//             }
//             result.setSuccessCount(successCount);
//             result.setFailedCount(failedCount);
//             if (failedCount == 0) {
//                 result.setStatus("SUCCESS");
//             } else if (successCount > 0) {
//                 result.setStatus("PARTIAL_SUCCESS");
//             } else {
//                 result.setStatus("FAILED");
//             }
//             logger.info("Processing completed: {}", result);
//         } catch (Exception e) {
//             result.setStatus("ERROR");
//             result.addError("File processing error: " + e.getMessage());
//             logger.error("Error processing file: {}", fileName, e);
//         }
//         return result;
//     }
//     private List<ExternalTradeDTO> parseFile(File file, String format) throws Exception {
//         List<ExternalTradeDTO> trades = new ArrayList<>();
//         switch (format.toLowerCase()) {
//             case "json":
//                 trades = parseJsonFile(file);
//                 break;
//             case "xml":
//                 trades = parseXmlFile(file);
//                 break;
//             case "csv":
//                 trades = parseCsvFile(file);
//                 break;
//             case "txt":
//                 trades = fixedWidthParserService.parseFixedWidthFile(file);
//                 break;
//             default:
//                 throw new IllegalArgumentException("Unsupported format: " + format);
//         }
//         return trades;
//     }
//     private List<ExternalTradeDTO> parseJsonFile(File file) throws Exception {
//         logger.info("=== PARSING JSON FILE ===");
//         logger.info("File: {}, Size: {} bytes", file.getName(), file.length());
        
//         ObjectMapper mapper = new ObjectMapper();
//         mapper.findAndRegisterModules();
//         if (file.length() == 0) {
//             return Collections.emptyList();
//         }
//         try {
//             ExternalTradeDTO[] array = mapper.readValue(file, ExternalTradeDTO[].class);
//             return Arrays.asList(array);
//         } catch (Exception arrayException) {
//             try {
//                 ExternalTradeListDTO wrapped = mapper.readValue(file, ExternalTradeListDTO.class);
//                 if (wrapped != null && wrapped.getOrders() != null && !wrapped.getOrders().isEmpty()) {
//                     return wrapped.getOrders();
//                 }
//             } catch (Exception wrappedException) {
//             }
//             try {
//                 ExternalTradeDTO single = mapper.readValue(file, ExternalTradeDTO.class);
//                 return Collections.singletonList(single);
//             } catch (Exception singleException) {
//                 try (BufferedReader br = new BufferedReader(new FileReader(file))) {
//                     List<ExternalTradeDTO> list = new ArrayList<>();
//                     String line;
//                     while ((line = br.readLine()) != null) {
//                         line = line.trim();
//                         if (line.isEmpty()) continue;
//                         ExternalTradeDTO dto = mapper.readValue(line, ExternalTradeDTO.class);
//                         list.add(dto);
//                     }
//                     if (!list.isEmpty()) return list;
//                 } catch (Exception jsonLinesEx) {
//                 }
//                 throw new Exception(
//                     "Invalid JSON format in file: " + file.getName() 
//                     + ". Expected JSON array, single object, wrapped array, or JSON lines."
//                 );
//             }
//         }
//     }
//     private List<ExternalTradeDTO> parseXmlFile(File file) throws Exception {
//         XmlMapper mapper = new XmlMapper();
//         try {
//             ExternalTradeDTO[] array = mapper.readValue(file, ExternalTradeDTO[].class);
//             if (array == null || array.length == 0) {
//                 return Collections.emptyList();
//             }
//             return Arrays.asList(array);
//         } catch (Exception e1) {
//             try {
//                 ExternalTradeDTO single = mapper.readValue(file, ExternalTradeDTO.class);
//                 return Arrays.asList(single);
//             } catch (Exception e2) {
//                 throw new Exception("Invalid XML format in file: " + file.getName(), e2);
//             }
//         }
//     }
//     private List<ExternalTradeDTO> parseCsvFile(File file) throws Exception {
//         logger.info("=== PARSING CSV FILE ===");
//         logger.info("File: {}, Size: {} bytes", file.getName(), file.length());
        
//         try (FileReader reader = new FileReader(file)) {
//             CsvToBean<ExternalTradeDTO> csvToBean = new CsvToBeanBuilder<ExternalTradeDTO>(reader)
//                     .withType(ExternalTradeDTO.class)
//                     .withIgnoreLeadingWhiteSpace(true)
//                     .build();
//             return csvToBean.parse();
//         }
//     }
//     private String getFileFormat(String fileName) {
//         int lastDot = fileName.lastIndexOf('.');
//         if (lastDot > 0) {
//             return fileName.substring(lastDot + 1);
//         }
//         return "unknown";
//     }
//     private CanonicalTrade convertToCanonicalTrade(ExternalTradeDTO dto) {
//         CanonicalTrade trade = new CanonicalTrade();
//         trade.setOriginatorType(parseOriginatorType(dto.getOriginatorType()));
//         trade.setFirmNumber(dto.getFirmNumber());
//         trade.setFundNumber(dto.getFundNumber());
//         trade.setTransactionType(dto.getTransactionType());
//         trade.setTransactionId(dto.getTransactionId());
//         trade.setTradeDateTime(parseDateTime(dto.getTradeDateTime()));
//         trade.setDollarAmount(dto.getDollarAmount());
//         trade.setClientAccountNo(dto.getClientAccountNo());
//         trade.setClientName(dto.getClientName());
//         trade.setSsn(dto.getSsn());
//         trade.setDob(parseDate(dto.getDob()));
//         trade.setShareQuantity(dto.getShareQuantity());
//         trade.setStatus("RECEIVED");
//         trade.setCreatedAt(LocalDateTime.now());
//         return trade;
//     }
//     private Integer parseOriginatorType(String value) {
//         if (value == null || value.isEmpty()) {
//             return null;
//         }
//         try {
//             return Integer.parseInt(value);
//         } catch (NumberFormatException e) {
//             return null;
//         }
//     }
//     private LocalDateTime parseDateTime(String value) {
//         if (value == null || value.isEmpty()) {
//             return null;
//         }
//         try {
//             return LocalDateTime.parse(value, DATE_TIME_FORMATTER);
//         } catch (Exception e) {
//             logger.warn("Failed to parse datetime: {}", value);
//             return null;
//         }
//     }
//     private LocalDate parseDate(String value) {
//         if (value == null || value.isEmpty()) {
//             return null;
//         }
//         try {
//             return LocalDate.parse(value, DATE_FORMATTER);
//         } catch (Exception e) {
//             logger.warn("Failed to parse date: {}", value);
//             return null;
//         }
//     }
    
//     /**
//      * Method to print comprehensive data information for debugging
//      */
//     public void printDataReceivingInfo() {
//         logger.info("=".repeat(80));
//         logger.info("TRADE PROCESSING SERVICE - DATA RECEIVING INFORMATION");
//         logger.info("=".repeat(80));
        
//         logger.info("SUPPORTED INPUT FORMATS:");
//         logger.info("1. JSON (.json) - Supports single object, array, wrapped array, or JSON lines");
//         logger.info("2. XML (.xml) - Supports single order or array of orders");  
//         logger.info("3. CSV (.csv) - Column-based format with headers");
//         logger.info("4. TXT (.txt) - Fixed-width format (130+ characters per line)");
        
//         logger.info("\nDATA FLOW:");
//         logger.info("File Input -> ExternalTradeDTO -> CanonicalTrade -> Database");
//         logger.info("NIO Channel Input -> CanonicalTrade (direct) -> Database");
        
//         logger.info("\nEXTERNAL TRADE DTO FIELDS:");
//         logger.info("- originatorType: String (converted to Integer)");
//         logger.info("- firmNumber: Integer");
//         logger.info("- fundNumber: Integer");
//         logger.info("- transactionType: String (B=Buy, S=Sell)");
//         logger.info("- transactionId: String");
//         logger.info("- tradeDateTime: String (format: yyyyMMddHHmmss)");
//         logger.info("- dollarAmount: BigDecimal");
//         logger.info("- clientAccountNo: Integer");
//         logger.info("- clientName: String");
//         logger.info("- ssn: String");
//         logger.info("- dob: String (format: yyyyMMdd or ddMMyyyy)");
//         logger.info("- shareQuantity: BigDecimal");
        
//         logger.info("\nCANONICAL TRADE ADDITIONAL FIELDS:");
//         logger.info("- fileId: UUID (assigned during processing)");
//         logger.info("- rawOrderId: UUID (assigned during processing)");
//         logger.info("- orderSource: String (source system identifier)");
//         logger.info("- status: String (RECEIVED, VALIDATED, VALIDATION_FAILED)");
//         logger.info("- createdAt: LocalDateTime");
//         logger.info("- validatedAt: LocalDateTime");
//         logger.info("- validationErrors: String");
        
//         logger.info("\nFIXED-WIDTH FORMAT POSITIONS:");
//         logger.info("Position 1-1:    OriginatorType");
//         logger.info("Position 2-5:    FirmNumber");
//         logger.info("Position 6-9:    FundNumber");
//         logger.info("Position 10-10:  TransactionType");
//         logger.info("Position 11-26:  TransactionId");
//         logger.info("Position 27-40:  TradeDateTime");
//         logger.info("Position 41-56:  DollarAmount (scaled by 100)");
//         logger.info("Position 57-76:  ClientAccountNo");
//         logger.info("Position 77-96:  ClientName");
//         logger.info("Position 97-105: SSN");
//         logger.info("Position 106-113: DOB");
//         logger.info("Position 114-129: ShareQuantity");
        
//         logger.info("=".repeat(80));
//     }
// }
package com.dfpt.canonical.service;
import com.dfpt.canonical.dto.ExternalTradeDTO;
import com.dfpt.canonical.dto.ExternalTradeListDTO;
import com.dfpt.canonical.dto.ProcessingResult;
import com.dfpt.canonical.dto.ValidationResult;
import com.dfpt.canonical.model.CanonicalTrade;
import com.dfpt.canonical.repository.CanonicalTradeRepository;
import com.dfpt.canonical.service.OutboxService;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.xml.XmlMapper;
import com.opencsv.bean.CsvToBean;
import com.opencsv.bean.CsvToBeanBuilder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.math.BigDecimal;
import java.nio.ByteBuffer;
import java.nio.channels.ReadableByteChannel;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Collections;
import java.util.UUID;
@Service
public class TradeProcessingService {
    private static final Logger logger = LoggerFactory.getLogger(TradeProcessingService.class);
    private static final DateTimeFormatter DATE_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmss");
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd");
    @Autowired
    private CanonicalTradeRepository tradeRepository;
    @Autowired
    private FixedWidthParserService fixedWidthParserService;
    @Autowired
    private ValidationService validationService;
    @Autowired
    private StatusStreamPublisher statusPublisher;
    
    @Autowired
    private OutboxService outboxService;
    
    public ProcessingResult processTradeFileFromChannel(ReadableByteChannel channel, String fileName, UUID fileId, String source) {
        ProcessingResult result = new ProcessingResult();
        result.setFileName(fileName);
        try {
            String format = getFileFormat(fileName);
            result.setFormat(format);
            if (!"txt".equalsIgnoreCase(format)) {
                result.setStatus("ERROR");
                result.addError("NIO channel processing only supports TXT (fixed-width) format");
                return result;
            }
            List<CanonicalTrade> trades = parseFixedWidthFromChannel(channel);
            result.setTotalRecords(trades.size());
            if (trades.isEmpty()) {
                result.setStatus("FAILED");
                result.addError("No records found");
                return result;
            }
            
            trades.forEach(trade -> {
                trade.setFileId(fileId);
                trade.setRawOrderId(UUID.randomUUID());
                trade.setOrderSource(source);
            });
            logger.info("Processing {} trades with fileId: {}, source: {}", trades.size(), fileId, source);
            
            int successCount = 0;
            int failedCount = 0;
            List<CanonicalTrade> savedTrades = new ArrayList<>();
            List<CanonicalTrade> validatedTrades = new ArrayList<>();  // Only successful validation trades
            
            logger.info("Starting validation for {} trades", trades.size());
            long validationStart = System.currentTimeMillis();
            
            for (int i = 0; i < trades.size(); i++) {
                CanonicalTrade canonical = trades.get(i);
                ValidationResult validationResult = validationService.validate(canonical);
                try {
                    if (canonical.getClientAccountNo() == null) {
                        canonical.setClientAccountNo(i + 1);
                    }
                    if (!validationResult.isValid() || !validationResult.getErrors().isEmpty()) {
                        canonical.setStatus("FAILED");
                        canonical.setValidationErrors(String.join("; ", validationResult.getErrors()));
                        result.addError("Trade " + (i + 1) + " validation failed: " + String.join("; ", validationResult.getErrors()));
                        failedCount++;
                    } else {
                        canonical.setStatus("VALIDATED");
                        successCount++;
                    }
                    canonical.setValidatedAt(LocalDateTime.now());
                    CanonicalTrade saved = tradeRepository.save(canonical);
                    result.addProcessedTrade(saved);
                    savedTrades.add(saved);
                    
                    // Only add successfully validated trades to outbox list
                    if ("VALIDATED".equals(saved.getStatus())) {
                        validatedTrades.add(saved);
                    }
                    
                    try {
                        statusPublisher.publishTradeStatus(saved);
                    } catch (Exception statusEx) {
                        logger.warn("Failed to publish status for trade {}: {}", saved.getTransactionId(), statusEx.getMessage());
                    }
                } catch (Exception e) {
                    failedCount++;
                    result.addError("Processing error for trade " + (i + 1) + ": " + e.getMessage());
                    logger.error("Trade processing failed", e);
                }
            }
            
            // Batch publish to outbox pattern - ONLY for successfully validated trades
            if (!validatedTrades.isEmpty()) {
                try {
                    logger.info("📤 About to create outbox entries for {} VALIDATED trades (out of {} total)", validatedTrades.size(), savedTrades.size());
                    outboxService.createOutboxEntries(validatedTrades);
                    logger.info("✅ Successfully created outbox entries for {} VALIDATED trades", validatedTrades.size());
                } catch (Exception outboxEx) {
                    logger.error("❌ Failed to create outbox entries for {} validated trades: {}", validatedTrades.size(), outboxEx.getMessage(), outboxEx);
                }
            } else {
                logger.warn("⚠️ No successfully validated trades found, skipping outbox entry creation");
            }
            long validationTime = System.currentTimeMillis() - validationStart;
            logger.info("Validation completed in {} ms - Success: {}, Failed: {}", validationTime, successCount, failedCount);
            result.setSuccessCount(successCount);
            result.setFailedCount(failedCount);
            if (failedCount == 0) {
                result.setStatus("SUCCESS");
            } else if (successCount > 0) {
                result.setStatus("PARTIAL_SUCCESS");
            } else {
                result.setStatus("FAILED");
            }
            
        
            logger.info("NIO Channel processing completed: {}", result);
        } catch (Exception e) {
            result.setStatus("ERROR");
            result.addError("Channel processing error: " + e.getMessage());
            logger.error("Error processing from channel: {}", fileName, e);
        }
        return result;
    }
    private List<CanonicalTrade> parseFixedWidthFromChannel(ReadableByteChannel channel) throws Exception {
        List<CanonicalTrade> trades = new ArrayList<>();
        ByteBuffer buffer = ByteBuffer.allocate(8192);
        StringBuilder lineBuilder = new StringBuilder();
        while (channel.read(buffer) != -1) {
            buffer.flip();
            while (buffer.hasRemaining()) {
                char c = (char) buffer.get();
                if (c == '\n') {
                    String line = lineBuilder.toString().trim();
                    if (!line.isEmpty() && line.length() >= 130) {
                        try {
                            CanonicalTrade trade = fixedWidthParserService.parseLineToCanonical(line);
                            if (trade != null) {
                                trades.add(trade);
                            }
                        } catch (Exception e) {
                            logger.warn("Failed to parse line: {}", line, e);
                        }
                    }
                    lineBuilder.setLength(0);
                } else if (c != '\r') {
                    lineBuilder.append(c);
                }
            }
            buffer.clear();
        }
        if (lineBuilder.length() > 0) {
            String line = lineBuilder.toString().trim();
            if (!line.isEmpty() && line.length() >= 130) {
                try {
                    CanonicalTrade trade = fixedWidthParserService.parseLineToCanonical(line);
                    if (trade != null) {
                        trades.add(trade);
                    }
                } catch (Exception e) {
                    logger.warn("Failed to parse final line: {}", line, e);
                }
            }
        }
        logger.info("Parsed {} trades from NIO channel", trades.size());
        return trades;
    }
    public ProcessingResult processTradeFile(String fileName) {
        ProcessingResult result = new ProcessingResult();
        result.setFileName(fileName);
        try {
            String format = getFileFormat(fileName);
            result.setFormat(format);
            File file = new File(fileName);
            List<ExternalTradeDTO> trades = parseFile(file, format);
            result.setTotalRecords(trades.size());
            if (trades.isEmpty()) {
                result.setStatus("FAILED");
                result.addError("No records found");
                return result;
            }
            int successCount = 0;
            int failedCount = 0;
            for (int i = 0; i < trades.size(); i++) {
                ExternalTradeDTO trade = trades.get(i);
                try {
                    if (trade.getClientAccountNo() == null) {
                        trade.setClientAccountNo(i + 1);
                    }
                    CanonicalTrade canonical = convertToCanonicalTrade(trade);
                    CanonicalTrade saved = tradeRepository.save(canonical);
                    successCount++;
                    result.addProcessedTrade(saved);
                } catch (Exception e) {
                    failedCount++;
                    result.addError("Processing error: " + e.getMessage());
                    logger.error("Trade processing failed", e);
                }
            }
            result.setSuccessCount(successCount);
            result.setFailedCount(failedCount);
            if (failedCount == 0) {
                result.setStatus("SUCCESS");
            } else if (successCount > 0) {
                result.setStatus("PARTIAL_SUCCESS");
            } else {
                result.setStatus("FAILED");
            }
            logger.info("Processing completed: {}", result);
        } catch (Exception e) {
            result.setStatus("ERROR");
            result.addError("File processing error: " + e.getMessage());
            logger.error("Error processing file: {}", fileName, e);
        }
        return result;
    }
    private List<ExternalTradeDTO> parseFile(File file, String format) throws Exception {
        List<ExternalTradeDTO> trades = new ArrayList<>();
        switch (format.toLowerCase()) {
            case "json":
                trades = parseJsonFile(file);
                break;
            case "xml":
                trades = parseXmlFile(file);
                break;
            case "csv":
                trades = parseCsvFile(file);
                break;
            case "txt":
                trades = fixedWidthParserService.parseFixedWidthFile(file);
                break;
            default:
                throw new IllegalArgumentException("Unsupported format: " + format);
        }
        return trades;
    }
    private List<ExternalTradeDTO> parseJsonFile(File file) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        mapper.findAndRegisterModules();
        if (file.length() == 0) {
            return Collections.emptyList();
        }
        try {
            ExternalTradeDTO[] array = mapper.readValue(file, ExternalTradeDTO[].class);
            return Arrays.asList(array);
        } catch (Exception arrayException) {
            try {
                ExternalTradeListDTO wrapped = mapper.readValue(file, ExternalTradeListDTO.class);
                if (wrapped != null && wrapped.getOrders() != null && !wrapped.getOrders().isEmpty()) {
                    return wrapped.getOrders();
                }
            } catch (Exception wrappedException) {
            }
            try {
                ExternalTradeDTO single = mapper.readValue(file, ExternalTradeDTO.class);
                return Collections.singletonList(single);
            } catch (Exception singleException) {
                try (BufferedReader br = new BufferedReader(new FileReader(file))) {
                    List<ExternalTradeDTO> list = new ArrayList<>();
                    String line;
                    while ((line = br.readLine()) != null) {
                        line = line.trim();
                        if (line.isEmpty()) continue;
                        ExternalTradeDTO dto = mapper.readValue(line, ExternalTradeDTO.class);
                        list.add(dto);
                    }
                    if (!list.isEmpty()) return list;
                } catch (Exception jsonLinesEx) {
                }
                throw new Exception(
                    "Invalid JSON format in file: " + file.getName() 
                    + ". Expected JSON array, single object, wrapped array, or JSON lines."
                );
            }
        }
    }
    private List<ExternalTradeDTO> parseXmlFile(File file) throws Exception {
        XmlMapper mapper = new XmlMapper();
        try {
            ExternalTradeDTO[] array = mapper.readValue(file, ExternalTradeDTO[].class);
            if (array == null || array.length == 0) {
                return Collections.emptyList();
            }
            return Arrays.asList(array);
        } catch (Exception e1) {
            try {
                ExternalTradeDTO single = mapper.readValue(file, ExternalTradeDTO.class);
                return Arrays.asList(single);
            } catch (Exception e2) {
                throw new Exception("Invalid XML format in file: " + file.getName(), e2);
            }
        }
    }
    private List<ExternalTradeDTO> parseCsvFile(File file) throws Exception {
        try (FileReader reader = new FileReader(file)) {
            CsvToBean<ExternalTradeDTO> csvToBean = new CsvToBeanBuilder<ExternalTradeDTO>(reader)
                    .withType(ExternalTradeDTO.class)
                    .withIgnoreLeadingWhiteSpace(true)
                    .build();
            return csvToBean.parse();
        }
    }
    private String getFileFormat(String fileName) {
        int lastDot = fileName.lastIndexOf('.');
        if (lastDot > 0) {
            return fileName.substring(lastDot + 1);
        }
        return "unknown";
    }
    private CanonicalTrade convertToCanonicalTrade(ExternalTradeDTO dto) {
        CanonicalTrade trade = new CanonicalTrade();
        trade.setOriginatorType(parseOriginatorType(dto.getOriginatorType()));
        trade.setFirmNumber(dto.getFirmNumber());
        trade.setFundNumber(dto.getFundNumber());
        trade.setTransactionType(dto.getTransactionType());
        trade.setTransactionId(dto.getTransactionId());
        trade.setTradeDateTime(parseDateTime(dto.getTradeDateTime()));
        trade.setDollarAmount(dto.getDollarAmount());
        trade.setClientAccountNo(dto.getClientAccountNo());
        trade.setClientName(dto.getClientName());
        trade.setSsn(dto.getSsn());
        trade.setDob(parseDate(dto.getDob()));
        trade.setShareQuantity(dto.getShareQuantity());
        trade.setStatus("RECEIVED");
        trade.setCreatedAt(LocalDateTime.now());
        return trade;
    }
    private Integer parseOriginatorType(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return null;
        }
    }
    private LocalDateTime parseDateTime(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        try {
            return LocalDateTime.parse(value, DATE_TIME_FORMATTER);
        } catch (Exception e) {
            logger.warn("Failed to parse datetime: {}", value);
            return null;
        }
    }
    private LocalDate parseDate(String value) {
        if (value == null || value.isEmpty()) {
            return null;
        }
        try {
            return LocalDate.parse(value, DATE_FORMATTER);
        } catch (Exception e) {
            logger.warn("Failed to parse date: {}", value);
            return null;
        }
    }


}
