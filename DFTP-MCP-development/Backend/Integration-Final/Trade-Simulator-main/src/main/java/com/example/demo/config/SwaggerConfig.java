package com.example.demo.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.Contact;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class SwaggerConfig {

    @Bean
    public OpenAPI tradeSimulatorOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("Trade Simulator API")
                        .description("API for simulating trade file uploads to S3 and message publishing to ActiveMQ")
                        .version("1.0.0")
                        .contact(new Contact()
                                .name("Trade Processing Team")
                                .email("support@dfpt.com")));
    }
}
