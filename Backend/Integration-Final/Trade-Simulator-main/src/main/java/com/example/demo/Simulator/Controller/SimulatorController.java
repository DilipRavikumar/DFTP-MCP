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
import org.springframework.web.multipart.MultipartFile;

import com.example.demo.Simulator.Service.S3UploadService;
import com.example.demo.Simulator.Service.SimulatorService;

import java.time.Instant;

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

    @PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    @Operation(summary = "Upload a single file to S3",
               description = "Upload a single multipart file and store it in the configured S3 bucket. Optionally supply `key`. Returns the S3 URL when successful.")
    @ApiResponses(value = {
        @ApiResponse(responseCode = "200", description = "File uploaded successfully"),
        @ApiResponse(responseCode = "400", description = "Bad request (no file)"),
        @ApiResponse(responseCode = "503", description = "S3 service not available/configured"),
        @ApiResponse(responseCode = "500", description = "Error during upload")
    })
    public ResponseEntity<String> uploadSingleFile(
            @RequestPart(name = "file", required = true) MultipartFile file,
            @RequestParam(name = "key", required = false) String key) {

        if (file == null || file.isEmpty()) {
            return ResponseEntity.status(HttpStatus.BAD_REQUEST).body("No file provided or file is empty");
        }

        if (s3UploadService == null) {
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body("S3UploadService not available. Make sure aws.s3.enabled=true and bean is created.");
        }

        try {
            // If no key provided -> create one using timestamp + original filename
            String finalKey = (key == null || key.trim().isEmpty())
                    ? Instant.now().toEpochMilli() + "_" + file.getOriginalFilename()
                    : key;

            byte[] content = file.getBytes();
            String url = s3UploadService.uploadFileFromBytes(finalKey, content);

            return ResponseEntity.ok(url);

        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body("Failed to upload file: " + e.getMessage());
        }
    }

}
