package com.example.status;

import com.example.status.dao.OrderStateHistoryDao;
import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.jdbc.DataSourceAutoConfiguration;
import org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.test.context.TestPropertySource;

@SpringBootTest
@EnableAutoConfiguration(exclude = {DataSourceAutoConfiguration.class, HibernateJpaAutoConfiguration.class})
@TestPropertySource(properties = {
    "spring.data.redis.host=localhost",
    "spring.data.redis.port=6379",
    "app.redis.stream=test-stream",
    "app.redis.group=test-group",
    "app.redis.consumer=test-consumer"
})
class StatusApplicationTests {

    @MockBean
    private OrderStateHistoryDao historyDao;

    @Test
    void contextLoads() {
    }
}