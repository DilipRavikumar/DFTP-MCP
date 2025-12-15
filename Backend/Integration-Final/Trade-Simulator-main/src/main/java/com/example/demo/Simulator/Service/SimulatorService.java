package com.example.demo.Simulator.Service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.List;

@Service
public class SimulatorService {

    @Autowired
    private FolderReader folderReader;

    @Autowired(required = false)
    private S3UploadService s3UploadService;

    private static final int MAX_RETRIES = 3;
    private static final long RETRY_DELAY_MS = 5000;

    public void run() throws Exception {

        List<File> files = folderReader.loadFiles();

        if (files.isEmpty()) {
            System.out.println("No files found");
            return;
        }

        for (File file : files) {

            System.out.println("Uploading to S3: " + file.getName());

            boolean success = false;

            String s3Key = "incoming/" + file.getName();

            for (int attempt = 1; attempt <= MAX_RETRIES; attempt++) {

                try {
                    if (s3UploadService != null) {
                        s3UploadService.uploadFile(file, s3Key);
                    } else {
                        System.out.println(" S3 upload disabled (local mode)");
                    }
                    System.out.println(" Uploaded on attempt " + attempt);
                    success = true;
                    break;

                } catch (Exception e) {
                    System.out.println(" Failed attempt " + attempt + " for file: " + file.getName());
                    System.out.println("   Reason: " + e.getMessage());

                    if (attempt < MAX_RETRIES) {
                        System.out.println("Retrying in 5 seconds...");
                        Thread.sleep(RETRY_DELAY_MS);
                    }
                }
            }

            if (!success) {
                System.out.println(" Moving file to /failed: " + file.getName());
                moveToFailed(file);
            }

            Thread.sleep(1000);
        }

        System.out.println(" All files processed.");
    }

    private void moveToFailed(File file) {
        try {
            File failedDir = new File("failed/");

            if (!failedDir.exists()) {
                failedDir.mkdirs();
            }

            Path targetPath = failedDir.toPath().resolve(file.getName());
            Files.move(file.toPath(), targetPath, StandardCopyOption.REPLACE_EXISTING);

            System.out.println(" File moved to failed: " + file.getName());

        } catch (Exception e) {
            System.out.println("Could not move file to failed: " + e.getMessage());
        }
    }
}