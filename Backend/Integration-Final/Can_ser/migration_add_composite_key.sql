-- Migration Script: Add Composite Key and Source Tracking to canonical_trades
-- Database: canonical_db
-- Date: 2025-12-03
-- Purpose: Allow same transaction_id from different raw orders (dual-mode processing)
--          Add order_source column to track MQ vs S3 without joining raw_orders

-- Connect to canonical_db database first
-- psql -U postgres -d canonical_db

-- Step 1: Drop old unique constraint on transaction_id
ALTER TABLE canonical_trades DROP CONSTRAINT IF EXISTS canonical_trades_transaction_id_key;

-- Step 2: Add raw_order_id column (if not exists)
ALTER TABLE canonical_trades ADD COLUMN IF NOT EXISTS raw_order_id UUID;

-- Step 3: Add order_source column (MQ or S3)
ALTER TABLE canonical_trades ADD COLUMN IF NOT EXISTS order_source VARCHAR(10);

-- Step 4: Create composite unique constraint
-- This allows same transaction_id from different raw_order_id sources
ALTER TABLE canonical_trades 
    ADD CONSTRAINT uk_raw_order_transaction 
    UNIQUE (raw_order_id, transaction_id);

-- Step 5: Create index on raw_order_id for query performance
CREATE INDEX IF NOT EXISTS idx_raw_order_id ON canonical_trades(raw_order_id);

-- Step 6: Create index on order_source for filtering
CREATE INDEX IF NOT EXISTS idx_order_source ON canonical_trades(order_source);

-- Verify the changes
SELECT 
    constraint_name, 
    constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'canonical_trades';

-- Check columns
SELECT 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name = 'canonical_trades' 
    AND column_name IN ('transaction_id', 'raw_order_id', 'order_source');
