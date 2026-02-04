-- Migration: Multi-User Authentication
-- Description: Adds user authentication and multi-tenancy support
-- Run this in Supabase SQL Editor

-- =====================================================
-- STEP 1: Create users table
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for faster email lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- =====================================================
-- STEP 2: Create linkedin_accounts table
-- =====================================================
CREATE TABLE IF NOT EXISTS linkedin_accounts (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    unipile_account_id VARCHAR(255),
    unipile_api_key_encrypted TEXT,
    linkedin_email VARCHAR(255),
    account_name VARCHAR(255),
    linkedin_profile_url VARCHAR(500),
    is_connected BOOLEAN DEFAULT false,
    connection_status VARCHAR(50),
    pending_checkpoint_type VARCHAR(50),
    connected_at TIMESTAMP,
    last_sync_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for faster user lookups
CREATE INDEX IF NOT EXISTS idx_linkedin_accounts_user_id ON linkedin_accounts(user_id);

-- =====================================================
-- STEP 3: Add user_id to leads table
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'leads' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE leads ADD COLUMN user_id VARCHAR(36) REFERENCES users(id);
        CREATE INDEX idx_leads_user_id ON leads(user_id);
    END IF;
END $$;

-- =====================================================
-- STEP 4: Add user_id to campaigns table
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'campaigns' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE campaigns ADD COLUMN user_id VARCHAR(36) REFERENCES users(id);
        CREATE INDEX idx_campaigns_user_id ON campaigns(user_id);
    END IF;
END $$;

-- =====================================================
-- STEP 5: Add user_id to business_profiles table
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'business_profiles' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE business_profiles ADD COLUMN user_id VARCHAR(36) REFERENCES users(id);
        CREATE INDEX idx_business_profiles_user_id ON business_profiles(user_id);
    END IF;
END $$;

-- =====================================================
-- STEP 6: Add user_id to automation_settings table
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'automation_settings' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE automation_settings ADD COLUMN user_id VARCHAR(36) UNIQUE REFERENCES users(id);
        CREATE INDEX idx_automation_settings_user_id ON automation_settings(user_id);
    END IF;
END $$;

-- =====================================================
-- STEP 7: Add user_id to invitation_logs table
-- =====================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'invitation_logs' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE invitation_logs ADD COLUMN user_id VARCHAR(36) REFERENCES users(id);
        CREATE INDEX idx_invitation_logs_user_id ON invitation_logs(user_id);
    END IF;
END $$;

-- =====================================================
-- VERIFICATION: Check all tables and columns exist
-- =====================================================
-- Run this to verify the migration worked:
-- SELECT table_name, column_name
-- FROM information_schema.columns
-- WHERE table_name IN ('users', 'linkedin_accounts', 'leads', 'campaigns', 'business_profiles', 'automation_settings', 'invitation_logs')
-- AND column_name = 'user_id'
-- ORDER BY table_name;
