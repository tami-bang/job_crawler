CREATE TABLE IF NOT EXISTS crawl_partitions (
    partition_key VARCHAR(100) PRIMARY KEY,
    request_payload_json TEXT NOT NULL,
    last_successful_watermark TIMESTAMPTZ,
    last_completed_page INTEGER DEFAULT 0,
    last_run_status VARCHAR(20) DEFAULT 'IDLE',
    last_job_count INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_postings (
    id SERIAL PRIMARY KEY,
    source VARCHAR(20) NOT NULL DEFAULT 'jobkorea',
    source_job_id VARCHAR(50) NOT NULL,
    stable_key VARCHAR(100) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    source_posted_at TIMESTAMPTZ NOT NULL,
    source_updated_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    list_content_hash VARCHAR(64) NOT NULL,
    raw_list_json TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    first_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_source_job_id UNIQUE (source, source_job_id)
);

CREATE INDEX IF NOT EXISTS idx_job_postings_source_posted_at ON job_postings(source_posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_postings_status ON job_postings(status);
CREATE INDEX IF NOT EXISTS idx_job_postings_stable_key ON job_postings(stable_key);

CREATE TABLE IF NOT EXISTS detail_fetch_queue (
    job_posting_id INTEGER PRIMARY KEY REFERENCES job_postings(id) ON DELETE CASCADE,
    priority INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    attempted_at TIMESTAMPTZ,
    lease_until TIMESTAMPTZ,
    last_error TEXT,
    reason VARCHAR(50) DEFAULT 'NEW',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_detail_queue_fetch
ON detail_fetch_queue(status, next_attempt_at, priority DESC);
