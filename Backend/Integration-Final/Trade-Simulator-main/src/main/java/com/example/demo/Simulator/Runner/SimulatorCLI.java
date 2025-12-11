package com.example.demo.Simulator.Runner;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import com.example.demo.Simulator.Service.DistributorSimulator;

@Component
public class SimulatorCLI implements ApplicationRunner {

    private final DistributorSimulator distributorSimulator;

    public SimulatorCLI(DistributorSimulator distributorSimulator) {
        this.distributorSimulator = distributorSimulator;
    }

    @Override
    public void run(ApplicationArguments args) throws Exception {
        System.out.println("=== Mutual Fund Order Simulator ===");
        System.out.println("Starting automatic order processing with random data...");

        distributorSimulator.send100Orders();

        System.out.println("All 100 random orders have been sent to MQ.");
        System.out.println("Application completed successfully.");
    }
}