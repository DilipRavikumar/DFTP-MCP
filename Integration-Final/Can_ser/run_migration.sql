-- Quick migration: Add missing columns and sequence to canonical_trades
-- Run this with: & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d canonical_db -f run_migration.sql

-- Add order_id column if it doesn't exist
ALTER TABLE canonical_trades ADD COLUMN IF NOT EXISTS order_id VARCHAR(20) UNIQUE;

-- Create sequence for order IDs
CREATE SEQUENCE IF NOT EXISTS canonical_order_seq START WITH 1 INCREMENT BY 1;

-- Create index on order_id
CREATE INDEX IF NOT EXISTS idx_order_id ON canonical_trades(order_id);

-- Create index on raw_order_id
CREATE INDEX IF NOT EXISTS idx_raw_order_id ON canonical_trades(raw_order_id);

-- Create index on order_source
CREATE INDEX IF NOT EXISTS idx_order_source ON canonical_trades(order_source);

-- Drop old unique constraint on transaction_id alone (if it exists)
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'canonical_trades_transaction_id_key') THEN
        ALTER TABLE canonical_trades DROP CONSTRAINT canonical_trades_transaction_id_key;
        RAISE NOTICE 'Dropped old unique constraint on transaction_id';
    ELSE
        RAISE NOTICE 'Old unique constraint not found - skipping';
    END IF;
END $$;

-- Verify columns exist
SELECT 
    column_name, 
    data_type, 
    character_maximum_length,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'canonical_trades' 
AND column_name IN ('order_id', 'raw_order_id', 'order_source')
ORDER BY column_name;

-- Verify sequence exists
SELECT sequence_name, start_value, increment 
FROM information_schema.sequences 
WHERE sequence_name = 'canonical_order_seq';

-- Show constraints
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'canonical_trades'::regclass;
