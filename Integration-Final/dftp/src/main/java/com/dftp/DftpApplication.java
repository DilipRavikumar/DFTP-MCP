package com.dftp;

import com.example.main.config.OutboxProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.jms.annotation.EnableJms;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication(scanBasePackages = {
        "com.dftp",  "com.example.main"
})
@EnableConfigurationProperties(OutboxProperties.class)
@EnableScheduling
@EnableJms
public class DftpApplication {

	public static void main(String[] args) {
		SpringApplication.run(DftpApplication.class, args);
	}

}
