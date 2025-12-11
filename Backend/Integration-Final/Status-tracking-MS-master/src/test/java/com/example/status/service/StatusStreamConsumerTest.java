package com.example.status.service;

import com.example.status.dao.OrderStateHistoryDao;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StreamOperations;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.*;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class StatusStreamConsumerTest {

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private OrderStateHistoryDao historyDao;

    @InjectMocks
    private StatusStreamConsumer statusStreamConsumer;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(statusStreamConsumer, "STREAM_KEY", "test-stream");
        ReflectionTestUtils.setField(statusStreamConsumer, "DLQ_STREAM", "test-dlq");
        ReflectionTestUtils.setField(statusStreamConsumer, "GROUP_NAME", "test-group");
        ReflectionTestUtils.setField(statusStreamConsumer, "CONSUMER_NAME", "test-consumer");
    }

    @Test
    void testParsePayload_ValidJson() throws Exception {
        Map<String, Object> expectedPayload = new HashMap<>();
        expectedPayload.put("sourceservice", "trade-capture");
        expectedPayload.put("status", "RECEIVED");
        
        String jsonPayload = objectMapper.writeValueAsString(expectedPayload);
        
        Map<String, Object> result = invokeParsePayload(jsonPayload);
        
        assertNotNull(result);
        assertEquals("trade-capture", result.get("sourceservice"));
        assertEquals("RECEIVED", result.get("status"));
    }

    @Test
    void testParsePayload_MapInput() {
        Map<String, Object> inputMap = new HashMap<>();
        inputMap.put("sourceservice", "trade-capture");
        inputMap.put("status", "RECEIVED");
        
        Map<String, Object> result = invokeParsePayload(inputMap);
        
        assertNotNull(result);
        assertEquals("trade-capture", result.get("sourceservice"));
        assertEquals("RECEIVED", result.get("status"));
    }

    @Test
    void testParsePayload_InvalidJson() {
        String invalidJson = "invalid json";
        
        Map<String, Object> result = invokeParsePayload(invalidJson);
        
        assertNull(result);
    }

    @Test
    void testExtractEventTime() {
        String recordId = "1234567890123-0";
        
        LocalDateTime result = invokeExtractEventTime(recordId);
        
        assertNotNull(result);
    }

    @Test
    void testGetStringValue_FirstFieldFound() {
        Map<String, Object> map = new HashMap<>();
        map.put("field1", "value1");
        map.put("field2", "value2");
        
        String result = invokeGetStringValue(map, "field1", "field2");
        
        assertEquals("value1", result);
    }

    @Test
    void testGetStringValue_SecondFieldFound() {
        Map<String, Object> map = new HashMap<>();
        map.put("field2", "value2");
        
        String result = invokeGetStringValue(map, "field1", "field2");
        
        assertEquals("value2", result);
    }

    @Test
    void testGetStringValue_NoFieldFound() {
        Map<String, Object> map = new HashMap<>();
        map.put("field3", "value3");
        
        String result = invokeGetStringValue(map, "field1", "field2");
        
        assertNull(result);
    }

    @Test
    void testGetIntValue_ValidInteger() {
        Map<String, Object> map = new HashMap<>();
        map.put("field1", "42");
        
        Integer result = invokeGetIntValue(map, "field1");
        
        assertEquals(42, result);
    }

    @Test
    void testGetIntValue_InvalidInteger() {
        Map<String, Object> map = new HashMap<>();
        map.put("field1", "invalid");
        
        Integer result = invokeGetIntValue(map, "field1");
        
        assertNull(result);
    }

    @Test
    void testToJson_ValidMap() {
        Map<Object, Object> map = new HashMap<>();
        map.put("key1", "value1");
        map.put("key2", "value2");
        
        String result = invokeToJson(map);
        
        assertTrue(result.contains("key1"));
        assertTrue(result.contains("value1"));
    }

    private Map<String, Object> invokeParsePayload(Object payloadObj) {
        return (Map<String, Object>) ReflectionTestUtils.invokeMethod(statusStreamConsumer, "parsePayload", payloadObj);
    }

    private LocalDateTime invokeExtractEventTime(String recordId) {
        return (LocalDateTime) ReflectionTestUtils.invokeMethod(statusStreamConsumer, "extractEventTime", recordId);
    }

    private String invokeGetStringValue(Map<String, Object> map, String... fieldNames) {
        return (String) ReflectionTestUtils.invokeMethod(statusStreamConsumer, "getStringValue", map, fieldNames);
    }

    private Integer invokeGetIntValue(Map<String, Object> map, String... fieldNames) {
        return (Integer) ReflectionTestUtils.invokeMethod(statusStreamConsumer, "getIntValue", map, fieldNames);
    }

    private String invokeToJson(Map<Object, Object> map) {
        return (String) ReflectionTestUtils.invokeMethod(statusStreamConsumer, "toJson", map);
    }
}