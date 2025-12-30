package com.example.demo.Simulator.Controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.responses.ApiResponse;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;


import com.example.demo.Simulator.Service.S3UploadService;
import com.example.demo.Simulator.Service.SimulatorService;

import java.time.Instant;
import java.util.Base64;
import java.util.Map;

@RestController
@RequestMapping("/simulate")
@Tag(name = "Trade Simulator", description = "Endpoints for simulating trade file processing and S3 uploads")
public class SimulatorController {

    private final S3UploadService s3UploadService;
    private final SimulatorService simulatorService;

    public SimulatorController(@Autowired(required = false) S3UploadService s3UploadService,
                               SimulatorService simulatorService) {
        this.s3UploadService = s3UploadService;
        this.simulatorService = simulatorService;
    }

    @GetMapping("/run")
    @Operation(
        summary = "Run trade file simulation",
        description = "Processes all files in the ./files directory and uploads them to S3. Each file is uploaded with retry logic (3 attempts). Failed uploads are moved to /failed directory."
    )
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "Simulation completed successfully"),
        @ApiResponse(responseCode = "500", description = "Error during simulation")
    })
    public String runSimulation() {
        try {
            simulatorService.run();
            return " Simulation complete. Check logs for per-file status.";
        } catch (Exception e) {
            e.printStackTrace();
            return " Error: " + e.getMessage();
        }
    }

    @PostMapping(
    value = "/upload",
    consumes = MediaType.APPLICATION_JSON_VALUE,
    produces = MediaType.APPLICATION_JSON_VALUE
)
@Operation(
    summary = "Upload a file to S3 (Base64 JSON)",
    description = "Uploads a file using Base64-encoded JSON payload instead of multipart"
)
@ApiResponses(value = {
    @ApiResponse(responseCode = "200", description = "File uploaded successfully"),
    @ApiResponse(responseCode = "400", description = "Bad request"),
    @ApiResponse(responseCode = "503", description = "S3 service not available"),
    @ApiResponse(responseCode = "500", description = "Upload failed")
})
public ResponseEntity<Map<String, String>> uploadSingleFile(
        @RequestBody Map<String, String> body) {

    String fileBase64 = body.get("fileBase64");
    String filename = body.get("filename");
    String key = body.get("key");

    if (fileBase64 == null || fileBase64.isBlank()) {
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(Map.of("result", "fileBase64 is required"));
    }

    if (filename == null || filename.isBlank()) {
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(Map.of("result", "filename is required"));
    }

    if (s3UploadService == null) {
        return ResponseEntity
                .status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of("result", "S3UploadService not available"));
    }

    try {
        byte[] content = Base64.getDecoder().decode(fileBase64);

        String finalKey =
                (key == null || key.isBlank())
                        ? Instant.now().toEpochMilli() + "_" + filename
                        : key;

        String url = s3UploadService.uploadFileFromBytes(finalKey, content);

        // 🔑 CRITICAL FIX — STRUCTURED OUTPUT
        return ResponseEntity.ok(
                Map.of("result", url)
        );

    } catch (IllegalArgumentException e) {
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(Map.of("result", "Invalid Base64 content"));

    } catch (Exception e) {
        e.printStackTrace();
        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(Map.of("result", "Failed to upload file: " + e.getMessage()));
    }
}

}
