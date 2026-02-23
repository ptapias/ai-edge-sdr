-- Migration: Add Sequences Feature
-- Date: 2026-02-23
-- Description: Creates tables for automated LinkedIn outreach sequences
-- Run against existing database: psql -U user -d dbname -f add_sequences.sql

-- ============================================
-- 1. Create sequences table
-- ============================================
CREATE TABLE IF NOT EXISTS sequences (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'draft',
    business_id VARCHAR(36) REFERENCES business_profiles(id),
    message_strategy VARCHAR(20) DEFAULT 'hybrid',
    total_enrolled INTEGER DEFAULT 0,
    active_enrolled INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    replied_count INTEGER DEFAULT 0,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_sequences_user_id ON sequences(user_id);
CREATE INDEX IF NOT EXISTS ix_sequences_status ON sequences(status);

-- ============================================
-- 2. Create sequence_steps table
-- ============================================
CREATE TABLE IF NOT EXISTS sequence_steps (
    id VARCHAR(36) PRIMARY KEY,
    sequence_id VARCHAR(36) NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    step_type VARCHAR(30) NOT NULL,
    delay_days INTEGER DEFAULT 0,
    prompt_context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_sequence_steps_sequence_id ON sequence_steps(sequence_id);

-- ============================================
-- 3. Create sequence_enrollments table
-- ============================================
CREATE TABLE IF NOT EXISTS sequence_enrollments (
    id VARCHAR(36) PRIMARY KEY,
    sequence_id VARCHAR(36) NOT NULL REFERENCES sequences(id),
    lead_id VARCHAR(36) NOT NULL REFERENCES leads(id),
    status VARCHAR(20) DEFAULT 'active',
    current_step_order INTEGER DEFAULT 1,
    last_step_completed_at TIMESTAMP,
    next_step_due_at TIMESTAMP,
    messages_sent TEXT,
    replied_at TIMESTAMP,
    completed_at TIMESTAMP,
    failed_reason TEXT,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id),
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_enrollment_lead_sequence UNIQUE (lead_id, sequence_id)
);

CREATE INDEX IF NOT EXISTS ix_sequence_enrollments_sequence_id ON sequence_enrollments(sequence_id);
CREATE INDEX IF NOT EXISTS ix_sequence_enrollments_lead_id ON sequence_enrollments(lead_id);
CREATE INDEX IF NOT EXISTS ix_sequence_enrollments_status ON sequence_enrollments(status);
CREATE INDEX IF NOT EXISTS ix_sequence_enrollments_user_id ON sequence_enrollments(user_id);
CREATE INDEX IF NOT EXISTS ix_sequence_enrollments_next_step ON sequence_enrollments(next_step_due_at);

-- ============================================
-- 4. Add active_sequence_id to leads table
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'active_sequence_id'
    ) THEN
        ALTER TABLE leads ADD COLUMN active_sequence_id VARCHAR(36);
    END IF;
END
$$;

-- ============================================
-- Done!
-- ============================================
-- Verify tables created:
-- SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'sequence%';
-- Verify column added:
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'leads' AND column_name = 'active_sequence_id';
