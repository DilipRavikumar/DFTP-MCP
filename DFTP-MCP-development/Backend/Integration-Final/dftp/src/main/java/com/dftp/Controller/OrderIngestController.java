//package com.dftp.Controller;
//
//import org.springframework.http.MediaType;
//import org.springframework.web.bind.annotation.PostMapping;
//import org.springframework.web.bind.annotation.RequestMapping;
//import org.springframework.web.bind.annotation.RequestParam;
//import org.springframework.web.bind.annotation.RequestPart;
//import org.springframework.web.bind.annotation.RestController;
//import org.springframework.web.multipart.MultipartFile;
//
//import com.dftp.Document.RawOrderDocument;
//import com.dftp.Service.OrderIngestService;
//
//import lombok.RequiredArgsConstructor;
//
//@RestController
//@RequestMapping("/ingest")
//@RequiredArgsConstructor
//public class OrderIngestController {
//
//    private final OrderIngestService ingestService;
//
//    @PostMapping("/mq")
//    public RawOrderDocument ingestFromMq(
//            @RequestParam String payload,
//            @RequestParam(defaultValue = "JSON") String payloadType
//    ) {
//        return ingestService.ingestFromMq(payload, payloadType);
//    }
//
//    @PostMapping(value = "/sftp", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
//    public RawOrderDocument ingestFile(@RequestPart("file") MultipartFile file) throws Exception {
//        return ingestService.ingestFile(file);
//    }
//}