DROP TABLE IF EXISTS canonical_trades CASCADE;
DROP TABLE IF EXISTS client CASCADE;
DROP TABLE IF EXISTS fund CASCADE;
CREATE TABLE IF NOT EXISTS client
(
    client_id INTEGER PRIMARY KEY,
    kyc_status VARCHAR(20) NOT NULL,  
    pan_number VARCHAR(20),
    status VARCHAR(20) NOT NULL,      
    type VARCHAR(20)                  
);
CREATE INDEX IF NOT EXISTS idx_clients_kyc_status ON client(kyc_status);
CREATE INDEX IF NOT EXISTS idx_clients_status ON client(status);
CREATE TABLE IF NOT EXISTS fund
(
    fund_id INTEGER PRIMARY KEY,
    scheme_code VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,      
    max_limit NUMERIC(18,2),
    min_limit NUMERIC(18,2)
);
CREATE INDEX IF NOT EXISTS idx_funds_scheme_code ON fund(scheme_code);
CREATE INDEX IF NOT EXISTS idx_funds_status ON fund(status);
CREATE TABLE IF NOT EXISTS canonical_trades
(
    id UUID PRIMARY KEY,
    status VARCHAR(50),                      
    created_at TIMESTAMP,
    originator_type INTEGER,
    firm_number INTEGER,
    fund_number INTEGER,
    transaction_type VARCHAR(10),            
    transaction_id VARCHAR(50),
    raw_order_id UUID,                       -- For MQ: from ingestion; For S3: generated per trade
    file_id UUID,                            -- For MQ: null; For S3: from ingestion (batch ID)
    order_source VARCHAR(10),                -- MQ or S3
    trade_datetime TIMESTAMP,
    dollar_amount NUMERIC(15,2),
    client_account_no INTEGER,
    client_name VARCHAR(100),
    ssn VARCHAR(20),
    dob DATE,
    share_quantity NUMERIC(15,2),
    validation_errors TEXT,                  
    validated_at TIMESTAMP,
    request_id VARCHAR(100),
    CONSTRAINT uk_raw_order_transaction UNIQUE (raw_order_id, transaction_id)
);
CREATE INDEX IF NOT EXISTS idx_transaction_id ON canonical_trades(transaction_id);
CREATE INDEX IF NOT EXISTS idx_trade_datetime ON canonical_trades(trade_datetime);
CREATE INDEX IF NOT EXISTS idx_client_account ON canonical_trades(client_account_no);
CREATE INDEX IF NOT EXISTS idx_fund_number ON canonical_trades(fund_number);
CREATE INDEX IF NOT EXISTS idx_status ON canonical_trades(status);
CREATE INDEX IF NOT EXISTS idx_request_id ON canonical_trades(request_id);
CREATE INDEX IF NOT EXISTS idx_raw_order_id ON canonical_trades(raw_order_id);
CREATE INDEX IF NOT EXISTS idx_file_id ON canonical_trades(file_id);
CREATE INDEX IF NOT EXISTS idx_order_source ON canonical_trades(order_source);

INSERT INTO client (client_id, kyc_status, pan_number, status, type) VALUES
(1,  'YES', 'ABCDE1234F', 'ACTIVE',    'INDIVIDUAL'),
(2,  'NO',  'PQRSX5678L', 'ACTIVE',    'CORPORATE'),
(3,  'YES', 'LMNOP3456Q', 'BLOCKED',   'INDIVIDUAL'),
(4,  'YES', 'QWERT6789A', 'ACTIVE',    'NRI'),
(5,  'NO',  'ZXCVB1122T', 'INACTIVE',  'INDIVIDUAL'),
(6,  'YES', 'ASDFG3344Y', 'ACTIVE',    'CORPORATE'),
(7,  'YES', 'HJKLP5566Z', 'ACTIVE',    'INDIVIDUAL'),
(8,  'NO',  'TYUIO7788M', 'BLOCKED',   'NRI'),
(9,  'YES', 'GHJKL8899N', 'ACTIVE',    'INDIVIDUAL'),
(10, 'YES', 'BNMJK9900P', 'INACTIVE',  'CORPORATE'),
(11, 'NO',  'ACDFG1212A', 'ACTIVE',    'INDIVIDUAL'),
(12, 'YES', 'PLMOK3434R', 'ACTIVE',    'NRI'),
(13, 'YES', 'OIUYT5656S', 'BLOCKED',   'CORPORATE'),
(14, 'NO',  'LKHGF7878D', 'INACTIVE',  'INDIVIDUAL'),
(15, 'YES', 'QAZWS9090E', 'ACTIVE',    'INDIVIDUAL'),
(16, 'YES', 'WSXED2323F', 'ACTIVE',    'CORPORATE'),
(17, 'NO',  'RFVTC4545G', 'INACTIVE',  'NRI'),
(18, 'YES', 'TGBNH6767H', 'ACTIVE',    'INDIVIDUAL'),
(19, 'YES', 'YHNJM8989J', 'ACTIVE',    'CORPORATE'),
(20, 'NO',  'UJMIK0101K', 'BLOCKED',   'INDIVIDUAL');
INSERT INTO fund (fund_id, scheme_code, status, max_limit, min_limit) VALUES
(1,  'SCH001', 'ACTIVE',   1000000, 1000),
(2,  'SCH002', 'ACTIVE',   500000,  500),
(3,  'SCH003', 'SUSPENDED',750000,  2000),
(4,  'SCH004', 'ACTIVE',   2000000, 5000),
(5,  'SCH005', 'CLOSED',   300000,  1000),
(6,  'SCH006', 'ACTIVE',   1500000, 2500),
(7,  'SCH007', 'ACTIVE',   900000,  1500),
(8,  'SCH008', 'SUSPENDED',400000,  1000),
(9,  'SCH009', 'ACTIVE',   1200000, 3000),
(10, 'SCH010', 'ACTIVE',   800000,  1200),
(11, 'SCH011', 'CLOSED',   600000,  900),
(12, 'SCH012', 'ACTIVE',   2500000, 5000),
(13, 'SCH013', 'ACTIVE',   1000000, 2000),
(14, 'SCH014', 'SUSPENDED',450000,  1500),
(15, 'SCH015', 'ACTIVE',   1700000, 3500),
(16, 'SCH016', 'ACTIVE',   1100000, 1800),
(17, 'SCH017', 'CLOSED',   700000,  2500),
(18, 'SCH018', 'ACTIVE',   1900000, 4000),
(19, 'SCH019', 'ACTIVE',   950000,  1200),
(20, 'SCH020', 'ACTIVE',   2200000, 6000);
