-- sql/ddl/schema.sql  —  Global Banking Revenue Intelligence
-- Compatible with Postgres (adjust types for Oracle)

CREATE TABLE IF NOT EXISTS dim_bank (
    bank_id          VARCHAR(12)  PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    region           VARCHAR(10)  NOT NULL,   -- US | India
    exchange         VARCHAR(20),
    index_membership VARCHAR(20),             -- SP500 | NIFTY50
    sector           VARCHAR(50),
    currency_native  VARCHAR(3)   NOT NULL,
    is_active        BOOLEAN      DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS stg_bank_records (
    stage_id          VARCHAR(36)  PRIMARY KEY,
    bank_id           VARCHAR(12)  NOT NULL REFERENCES dim_bank(bank_id),
    period            VARCHAR(10)  NOT NULL,
    net_revenue_usd   NUMERIC(14,2) NOT NULL,
    net_income_usd    NUMERIC(14,2),
    total_assets_usd  NUMERIC(16,2),
    nim_pct           NUMERIC(6,2),
    roe_pct           NUMERIC(6,2),
    tier1_ratio       NUMERIC(6,2),
    fx_rate_used      NUMERIC(8,4) NOT NULL DEFAULT 1.0,
    dq_status         VARCHAR(10)  NOT NULL,
    source_ref        VARCHAR(100),
    loaded_at         TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (bank_id, period)
);

CREATE TABLE IF NOT EXISTS global_bank_fact (
    fact_id             VARCHAR(36)  PRIMARY KEY,
    bank_id             VARCHAR(12)  NOT NULL REFERENCES dim_bank(bank_id),
    period              VARCHAR(10)  NOT NULL,
    net_revenue_usd     NUMERIC(14,2) NOT NULL,
    net_income_usd      NUMERIC(14,2),
    total_assets_usd    NUMERIC(16,2),
    nim_pct             NUMERIC(6,2),
    roe_pct             NUMERIC(6,2),
    tier1_ratio         NUMERIC(6,2),
    -- derived
    net_margin_pct      NUMERIC(6,2),
    revenue_rank        SMALLINT,
    region_rank         SMALLINT,
    yoy_revenue_pct     NUMERIC(8,2),
    qoq_revenue_pct     NUMERIC(8,2),
    -- audit
    stage_id            VARCHAR(36)  REFERENCES stg_bank_records(stage_id),
    loaded_at           TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (bank_id, period)
);

CREATE TABLE IF NOT EXISTS peer_comparison_mart (
    mart_id              VARCHAR(36) PRIMARY KEY,
    period               VARCHAR(10) NOT NULL,
    bank_id              VARCHAR(12) NOT NULL,
    net_revenue_usd      NUMERIC(14,2),
    net_margin_pct       NUMERIC(6,2),
    roe_pct              NUMERIC(6,2),
    tier1_ratio          NUMERIC(6,2),
    revenue_rank_global  SMALLINT,
    revenue_rank_region  SMALLINT,
    vs_gs_revenue_pct    NUMERIC(8,2),   -- % diff vs Goldman Sachs
    refreshed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (period, bank_id)
);

CREATE TABLE IF NOT EXISTS dq_check_results (
    check_id       VARCHAR(36) PRIMARY KEY,
    table_name     VARCHAR(100),
    check_type     VARCHAR(40),
    run_timestamp  TIMESTAMP,
    rows_loaded    INTEGER,
    fail_count     INTEGER,
    status         VARCHAR(10),
    alert_sent     BOOLEAN,
    detail         TEXT
);

CREATE TABLE IF NOT EXISTS field_lineage (
    lineage_id      VARCHAR(36) PRIMARY KEY,
    target_entity   VARCHAR(100),
    target_field    VARCHAR(100),
    source_entity   VARCHAR(100),
    source_fields   TEXT,
    transform_logic TEXT,
    transform_type  VARCHAR(20),
    recorded_at     TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_fact_period   ON global_bank_fact (period);
CREATE INDEX IF NOT EXISTS idx_fact_bank     ON global_bank_fact (bank_id);
CREATE INDEX IF NOT EXISTS idx_mart_period   ON peer_comparison_mart (period);
