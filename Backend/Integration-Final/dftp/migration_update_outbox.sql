-- Migration script to rename 'source' column to 'order_type' in outbox_events table
-- Run this on the ingestion_db database

-- Check current column name
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'outbox_events' 
  AND column_name IN ('source', 'order_type');

-- Rename the column
ALTER TABLE outbox_events RENAME COLUMN source TO order_type;

-- Verify the change
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'outbox_events' 
  AND column_name = 'order_type';

-- Check sample data
SELECT id, raw_order_id, order_type, event_type, status 
FROM outbox_events 
ORDER BY created_at DESC 
LIMIT 5;
