-- Migration Script: Update Schema for File ID and Order ID Changes
-- Database: canonical_db
-- Date: 2025-12-03
-- Purpose: 
--   - Remove order_id column (no longer used)
--   - Add file_id column (For MQ: null; For S3: batch ID from ingestion)
--   - Update raw_order_id logic (For MQ: from ingestion; For S3: generated per trade)

-- Step 1: Drop old unique constraint on transaction_id (if exists)
ALTER TABLE canonical_trades DROP CONSTRAINT IF EXISTS canonical_trades_transaction_id_key;

-- Step 2: Add raw_order_id column if not exists
ALTER TABLE canonical_trades ADD COLUMN IF NOT EXISTS raw_order_id UUID;

-- Step 3: Add file_id column if not exists  
ALTER TABLE canonical_trades ADD COLUMN IF NOT EXISTS file_id UUID;

-- Step 4: Add order_source column if not exists
ALTER TABLE canonical_trades ADD COLUMN IF NOT EXISTS order_source VARCHAR(10);

-- Step 5: Remove order_id column if exists (no longer used)
ALTER TABLE canonical_trades DROP COLUMN IF EXISTS order_id;

-- Step 6: Drop sequence if exists (no longer used)
DROP SEQUENCE IF EXISTS canonical_order_seq;

-- Step 7: Ensure composite unique constraint exists
ALTER TABLE canonical_trades DROP CONSTRAINT IF EXISTS uk_raw_order_transaction;
ALTER TABLE canonical_trades ADD CONSTRAINT uk_raw_order_transaction 
    UNIQUE (raw_order_id, transaction_id);

-- Step 8: Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_raw_order_id ON canonical_trades(raw_order_id);
CREATE INDEX IF NOT EXISTS idx_file_id ON canonical_trades(file_id);
CREATE INDEX IF NOT EXISTS idx_order_source ON canonical_trades(order_source);

-- Verification queries
SELECT 'Migration completed successfully' AS status;

-- Check columns
SELECT 
    column_name, 
    data_type, 
    is_nullable 
FROM information_schema.columns 
WHERE table_name = 'canonical_trades' 
    AND column_name IN ('transaction_id', 'raw_order_id', 'file_id', 'order_source', 'order_id')
ORDER BY ordinal_position;

-- Check constraints
SELECT 
    constraint_name, 
    constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'canonical_trades';
