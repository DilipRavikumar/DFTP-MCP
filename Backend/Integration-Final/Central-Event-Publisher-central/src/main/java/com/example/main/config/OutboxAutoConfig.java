package com.example.main.config;


import javax.sql.DataSource;

import org.apache.activemq.ActiveMQConnectionFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.ComponentScan;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jms.core.JmsTemplate;
import org.springframework.scheduling.annotation.EnableScheduling;

import com.example.main.core.GenericOutboxRepository;
import com.example.main.core.MongoOutboxRepository;
import com.example.main.core.OutboxMessagePublisher;
import com.example.main.core.OutboxProcessor;

@Configuration
@EnableConfigurationProperties(OutboxProperties.class)
@ComponentScan(basePackages = "com.example.main")
@EnableScheduling
public class OutboxAutoConfig {

    @Bean
    @ConditionalOnMissingBean
    public ActiveMQConnectionFactory activeMQConnectionFactory(OutboxProperties props) {
        ActiveMQConnectionFactory f = new ActiveMQConnectionFactory();
        f.setBrokerURL(props.getBrokerUrl());
        if (props.getUsername() != null) f.setUserName(props.getUsername());
        if (props.getPassword() != null) f.setPassword(props.getPassword());
        return f;
    }

    @Bean
    @ConditionalOnMissingBean
    public JmsTemplate jmsTemplate(ActiveMQConnectionFactory factory) {
        return new JmsTemplate(factory);
    }

    @Configuration
    @ConditionalOnClass(JdbcTemplate.class)
    @ConditionalOnProperty(name = "outbox.database-type", havingValue = "JDBC", matchIfMissing = true)
    static class JdbcOutboxConfig {
        
        @Bean
        @ConditionalOnMissingBean
        public GenericOutboxRepository genericOutboxRepository(DataSource ds, OutboxProperties props) {
            return new GenericOutboxRepository(new JdbcTemplate(ds), props.getTableName());
        }

        @Bean
        @ConditionalOnMissingBean
        public OutboxProcessor outboxProcessor(GenericOutboxRepository repo,
                                              OutboxMessagePublisher publisher,
                                              OutboxProperties props) {
            return new OutboxProcessor(repo, null, publisher, props);
        }
    }

    @Configuration
    @ConditionalOnClass(MongoTemplate.class)
    @ConditionalOnProperty(name = "outbox.database-type", havingValue = "MONGODB")
    static class MongoOutboxConfig {
        
        @Bean
        @ConditionalOnMissingBean
        public MongoOutboxRepository mongoOutboxRepository(MongoTemplate mongoTemplate, OutboxProperties props) {
            return new MongoOutboxRepository(mongoTemplate, props.getTableName());
        }

        @Bean
        @ConditionalOnMissingBean
        public OutboxProcessor outboxProcessor(MongoOutboxRepository repo,
                                              OutboxMessagePublisher publisher,
                                              OutboxProperties props) {
            return new OutboxProcessor(null, repo, publisher, props);
        }
    }
}
