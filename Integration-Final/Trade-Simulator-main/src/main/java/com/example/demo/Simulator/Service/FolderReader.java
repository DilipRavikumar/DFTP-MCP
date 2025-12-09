package com.example.demo.Simulator.Service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;

@Service
public class FolderReader {

    @Value("${simulator.resource-folder}")
    private String resourceFolder;

    public List<File> loadFiles() {

        File folder = new File(resourceFolder);

        if (!folder.exists()) {
            System.out.println("Folder does not exist: " + folder.getAbsolutePath());
            return List.of();
        }

        File[] files = folder.listFiles();
        if (files == null) {
            return List.of();
        }

        return Arrays.stream(files)
                .sorted(Comparator.comparing(File::getName))
                .toList();
    }
}