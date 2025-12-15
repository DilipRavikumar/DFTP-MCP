-- Database initialization script for Can_ser service
-- This script runs when PostgreSQL container starts for the first time

-- Ensure the database exists (usually handled by POSTGRES_DB env var)
-- CREATE DATABASE IF NOT EXISTS canonical_db;

-- Create any additional database objects, indexes, or initial data here
-- Note: Hibernate will create tables automatically with ddl-auto: update

-- Create additional indexes for better performance
CREATE INDEX IF NOT EXISTS idx_canonical_trades_created_at 
ON canonical_trades (created_at);

CREATE INDEX IF NOT EXISTS idx_canonical_trades_status_created_at 
ON canonical_trades (status, created_at);

CREATE INDEX IF NOT EXISTS idx_canonical_trades_validated_at 
ON canonical_trades (validated_at);

CREATE INDEX IF NOT EXISTS idx_canonical_trades_order_source 
ON canonical_trades (order_source);

-- Create a sequence for generating unique transaction IDs if needed
CREATE SEQUENCE IF NOT EXISTS transaction_id_seq 
START WITH 1000000 
INCREMENT BY 1;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE canonical_db TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;

-- Log initialization completion
DO $$
BEGIN
    RAISE NOTICE 'Can_ser database initialization completed successfully!';
END $$;