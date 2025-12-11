-- Create outbox table for reliable event delivery
-- This table stores events before they are sent to Redis streams
-- Status flow: NEW -> SENT (or FAILED with retries)

CREATE TABLE IF NOT EXISTS outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id UUID NOT NULL UNIQUE,  -- Trade ID reference
    trade_datetime TIMESTAMP NOT NULL,  -- Trade datetime for cutoff logic
    payload JSONB NOT NULL,            -- JSON representation of trade data
    status VARCHAR(20) NOT NULL DEFAULT 'NEW', -- NEW, SENT, FAILED
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_attempt_at TIMESTAMP,         -- Last retry attempt timestamp
    retry_count INTEGER NOT NULL DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox(status);
CREATE INDEX IF NOT EXISTS idx_outbox_created_at ON outbox(created_at);
CREATE INDEX IF NOT EXISTS idx_outbox_retry_status ON outbox(status, retry_count);
CREATE INDEX IF NOT EXISTS idx_outbox_trade_datetime ON outbox(trade_datetime);

-- Comments for documentation
COMMENT ON TABLE outbox IS 'Outbox pattern table for reliable event delivery to Redis streams';
COMMENT ON COLUMN outbox.id IS 'Primary key for outbox record';
COMMENT ON COLUMN outbox.aggregate_id IS 'Foreign key reference to trade ID';
COMMENT ON COLUMN outbox.trade_datetime IS 'Trade datetime for business cutoff logic';
COMMENT ON COLUMN outbox.payload IS 'Complete trade data as JSON for event publishing';
COMMENT ON COLUMN outbox.status IS 'Event status: NEW (ready to send), SENT (delivered), FAILED (retry needed)';
COMMENT ON COLUMN outbox.created_at IS 'Timestamp when event was created in outbox';
COMMENT ON COLUMN outbox.last_attempt_at IS 'Timestamp of last delivery attempt (for retry logic)';
COMMENT ON COLUMN outbox.retry_count IS 'Number of failed delivery attempts';