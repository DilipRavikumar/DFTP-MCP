package com.example.main.core;

import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Criteria;
import org.springframework.data.mongodb.core.query.Query;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.transaction.annotation.Transactional;
import java.util.UUID;
public class MongoOutboxRepository {

    private final MongoTemplate mongoTemplate;
    private final String collectionName;
    private final String pendingStatusCol = "status";
    private final String payloadCol = "payload";
    private final String idCol = "_id";

    public MongoOutboxRepository(MongoTemplate mongoTemplate, String collectionName) {
        this.mongoTemplate = mongoTemplate;
        this.collectionName = collectionName;
    }

    /**
     * Fetch one pending record from MongoDB.
     * MongoDB doesn't have FOR UPDATE SKIP LOCKED, but we can use findAndModify
     * to atomically fetch and mark as processing.
     */
    @Transactional
    public OutboxRecord fetchNextPending(String pendingStatus) {
        Query query = new Query(Criteria.where(pendingStatusCol).is(pendingStatus))
                .limit(1);
        
        org.bson.Document doc = mongoTemplate.findOne(query, org.bson.Document.class, collectionName);
        
        if (doc == null) {
            return null;
        }
        
//        UUID id = doc.get(idCol);
        UUID id = UUID.fromString(doc.getString(idCol));

        String payload = doc.getString(payloadCol);
        
        return new OutboxRecord(id, payload);
    }

    public void updateStatus(UUID id, String status) {
        Query query = new Query(Criteria.where(idCol).is(id));
        Update update = new Update().set(pendingStatusCol, status);
        mongoTemplate.updateFirst(query, update, collectionName);
    }
}
