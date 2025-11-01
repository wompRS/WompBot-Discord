-- GDPR Compliance Migration
-- Add tables and columns for GDPR compliance (Art. 6, 7, 15, 17, 20)

-- Consent tracking table (GDPR Art. 6 - Lawful basis for processing)
CREATE TABLE IF NOT EXISTS user_consent (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255) NOT NULL,
    consent_given BOOLEAN DEFAULT FALSE,
    consent_date TIMESTAMP,
    consent_withdrawn BOOLEAN DEFAULT FALSE,
    consent_withdrawn_date TIMESTAMP,
    consent_version VARCHAR(20) DEFAULT '1.0', -- Track policy version user consented to
    ip_address VARCHAR(45), -- For audit purposes (optional)
    consent_method VARCHAR(50), -- 'command', 'first_message', 'explicit'
    extended_retention BOOLEAN DEFAULT FALSE, -- User opted in to longer data retention
    marketing_consent BOOLEAN DEFAULT FALSE, -- For any future marketing features
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data processing audit log (GDPR Art. 30 - Records of processing activities)
CREATE TABLE IF NOT EXISTS data_audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    action VARCHAR(100) NOT NULL, -- 'export', 'delete', 'consent_given', 'consent_withdrawn', 'data_access'
    action_details TEXT,
    performed_by_user_id BIGINT, -- Who performed the action (user or admin)
    ip_address VARCHAR(45),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data export requests (GDPR Art. 15 - Right of access)
CREATE TABLE IF NOT EXISTS data_export_requests (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_date TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    export_file_path TEXT, -- Temporary file path (deleted after 48h)
    download_count INT DEFAULT 0,
    expires_at TIMESTAMP, -- Export link expires after 48 hours
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data deletion requests (GDPR Art. 17 - Right to erasure)
CREATE TABLE IF NOT EXISTS data_deletion_requests (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_deletion_date TIMESTAMP, -- 30-day grace period
    completed_date TIMESTAMP,
    cancelled_date TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'scheduled', 'completed', 'cancelled'
    deletion_reason TEXT,
    data_retained_for_legal JSONB, -- What data was retained for legal obligations
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data breach log (GDPR Art. 33, 34 - Breach notification)
CREATE TABLE IF NOT EXISTS data_breach_log (
    id SERIAL PRIMARY KEY,
    breach_date TIMESTAMP NOT NULL,
    discovery_date TIMESTAMP NOT NULL,
    breach_type VARCHAR(100) NOT NULL, -- 'confidentiality', 'integrity', 'availability'
    affected_users_count INT DEFAULT 0,
    affected_user_ids BIGINT[], -- Array of affected user IDs
    breach_description TEXT NOT NULL,
    containment_actions TEXT,
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_date TIMESTAMP,
    authority_notified BOOLEAN DEFAULT FALSE,
    authority_notification_date TIMESTAMP,
    severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    resolved BOOLEAN DEFAULT FALSE,
    resolved_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Privacy policy versions (track changes over time)
CREATE TABLE IF NOT EXISTS privacy_policy_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(20) NOT NULL UNIQUE,
    effective_date TIMESTAMP NOT NULL,
    policy_text TEXT NOT NULL,
    summary TEXT, -- Short summary of changes
    previous_version VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data retention schedule (GDPR Art. 5 - Storage limitation)
CREATE TABLE IF NOT EXISTS data_retention_config (
    id SERIAL PRIMARY KEY,
    data_type VARCHAR(100) NOT NULL UNIQUE, -- 'messages', 'behavior_analysis', 'claims', etc.
    retention_days INT NOT NULL,
    legal_basis TEXT, -- Explanation for retention period
    auto_delete_enabled BOOLEAN DEFAULT TRUE,
    last_cleanup_run TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default retention periods
INSERT INTO data_retention_config (data_type, retention_days, legal_basis, auto_delete_enabled) VALUES
    ('messages', 365, 'Legitimate interest for chat statistics and context', FALSE),
    ('user_behavior', 365, 'Legitimate interest for abuse prevention', FALSE),
    ('claims', 1825, 'User-generated content with community value (5 years)', FALSE),
    ('quotes', 1825, 'User-generated content with community value (5 years)', FALSE),
    ('hot_takes', 1825, 'Public statements with historical value (5 years)', FALSE),
    ('search_logs', 90, 'Service improvement and analytics (90 days)', FALSE),
    ('fact_checks', 730, 'Educational and transparency purposes (2 years)', FALSE),
    ('stats_cache', 30, 'Performance optimization only (30 days)', TRUE),
    ('audit_logs', 2555, 'Legal and security requirements (7 years)', FALSE),
    ('debate_records', 1095, 'Community engagement history (3 years)', FALSE)
ON CONFLICT (data_type) DO NOTHING;

-- Insert initial privacy policy version
INSERT INTO privacy_policy_versions (version, effective_date, policy_text, summary, is_active) VALUES
    ('1.0', CURRENT_TIMESTAMP,
    'WompBot Privacy Policy v1.0

1. DATA CONTROLLER
   WompBot Discord Bot ("we", "our", or "the bot")
   Contact: [Bot Administrator Contact]

2. DATA WE COLLECT
   - Discord User IDs (permanent identifier)
   - Usernames and display names
   - Message content and metadata (timestamps, channels)
   - User interaction patterns (replies, mentions)
   - Behavioral analysis data (tone, engagement patterns)
   - Claims, quotes, and hot takes you make
   - Search queries and command usage
   - iRacing profile linkage (if you use /iracing_link)
   - Debate participation and analysis

3. LEGAL BASIS FOR PROCESSING (GDPR Art. 6)
   - Consent: You provide explicit consent when using the bot
   - Legitimate Interest: Server statistics and abuse prevention
   - Contract: Providing requested features (reminders, stats)

4. HOW WE USE YOUR DATA
   - Generate server statistics and analytics
   - Provide personalized features (wrapped, stats)
   - Track claims and enable fact-checking
   - Maintain chat context for AI features
   - Prevent abuse and ensure community safety
   - Improve bot features and functionality

5. DATA SHARING
   We share data with these third parties:
   - OpenRouter/LLM Providers: For AI analysis (anonymized when possible)
   - Tavily: For fact-checking searches
   - iRacing API: For racing statistics (only if you link accounts)

   We do NOT sell your data to third parties.

6. YOUR RIGHTS (GDPR)
   - Right of Access (Art. 15): /download_my_data
   - Right to Erasure (Art. 17): /delete_my_data
   - Right to Rectification: /update_my_data
   - Right to Data Portability (Art. 20): JSON export
   - Right to Object: /opt_out
   - Right to Withdraw Consent: /withdraw_consent

7. DATA RETENTION
   - Messages: 1 year (configurable)
   - Behavior analysis: 1 year
   - Public content (claims, quotes): 5 years
   - Audit logs: 7 years (legal requirement)
   - Opted-out users: Immediate deletion

8. DATA SECURITY
   - Encrypted credentials (Fernet/AES-256)
   - Parameterized database queries
   - Access controls and audit logging
   - Regular security updates
   - No publicly exposed services

9. INTERNATIONAL TRANSFERS
   Data is stored on servers located in [SPECIFY REGION].
   Standard Contractual Clauses (SCCs) apply for EU data.

10. COOKIES AND TRACKING
    We do not use cookies. Discord handles authentication.

11. CHILDREN''S PRIVACY
    Per Discord TOS, users must be 13+. We do not knowingly
    collect data from children under 13.

12. BREACH NOTIFICATION
    We will notify you within 72 hours of discovering any
    data breach affecting your personal information.

13. POLICY CHANGES
    We will notify you of material changes via Discord.
    Continued use constitutes acceptance.

14. CONTACT & COMPLAINTS
    - Privacy concerns: Use /privacy_support
    - EU Supervisory Authority: [Your DPA]
    - Data Protection Officer: [If applicable]

Last Updated: ' || CURRENT_TIMESTAMP,
    'Initial GDPR-compliant privacy policy', TRUE)
ON CONFLICT (version) DO NOTHING;

-- Add GDPR-related indexes
CREATE INDEX IF NOT EXISTS idx_user_consent_user_id ON user_consent(user_id);
CREATE INDEX IF NOT EXISTS idx_user_consent_consent_given ON user_consent(consent_given);
CREATE INDEX IF NOT EXISTS idx_data_audit_log_user_id ON data_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_data_audit_log_timestamp ON data_audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_data_audit_log_action ON data_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_data_export_requests_user_id ON data_export_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_data_export_requests_status ON data_export_requests(status);
CREATE INDEX IF NOT EXISTS idx_data_deletion_requests_user_id ON data_deletion_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_data_deletion_requests_status ON data_deletion_requests(status);
CREATE INDEX IF NOT EXISTS idx_data_deletion_scheduled ON data_deletion_requests(scheduled_deletion_date)
    WHERE status = 'scheduled';

-- Add consent tracking to existing user_profiles table
ALTER TABLE user_profiles
    ADD COLUMN IF NOT EXISTS consent_given BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS consent_date TIMESTAMP,
    ADD COLUMN IF NOT EXISTS data_processing_allowed BOOLEAN DEFAULT TRUE;

-- Create view for GDPR-compliant user data export
CREATE OR REPLACE VIEW user_data_export_view AS
SELECT
    up.user_id,
    up.username,
    up.total_messages,
    up.first_seen,
    up.last_seen,
    up.opted_out,
    uc.consent_given,
    uc.consent_date,
    COUNT(DISTINCT m.message_id) as message_count,
    COUNT(DISTINCT c.id) as claim_count,
    COUNT(DISTINCT q.id) as quote_count,
    COUNT(DISTINCT ht.id) as hot_take_count,
    COUNT(DISTINCT d.id) as debate_count
FROM user_profiles up
LEFT JOIN user_consent uc ON up.user_id = uc.user_id
LEFT JOIN messages m ON up.user_id = m.user_id AND m.opted_out = FALSE
LEFT JOIN claims c ON up.user_id = c.user_id
LEFT JOIN quotes q ON up.user_id = q.user_id
LEFT JOIN hot_takes ht ON c.id = ht.claim_id
LEFT JOIN debate_participants dp ON up.user_id = dp.user_id
LEFT JOIN debates d ON dp.debate_id = d.id
GROUP BY up.user_id, up.username, up.total_messages, up.first_seen, up.last_seen,
         up.opted_out, uc.consent_given, uc.consent_date;

-- Function to anonymize user data (for legal retention requirements)
CREATE OR REPLACE FUNCTION anonymize_user_data(target_user_id BIGINT)
RETURNS VOID AS $$
BEGIN
    -- Replace usernames with anonymized version
    UPDATE messages SET
        username = 'User_' || target_user_id || '_Deleted',
        content = '[Content Deleted - User Request]'
    WHERE user_id = target_user_id;

    UPDATE claims SET
        username = 'User_' || target_user_id || '_Deleted',
        claim_text = '[Claim Deleted - User Request]'
    WHERE user_id = target_user_id;

    UPDATE quotes SET
        username = 'User_' || target_user_id || '_Deleted',
        quote_text = '[Quote Deleted - User Request]'
    WHERE user_id = target_user_id;

    -- Keep audit logs but anonymize
    UPDATE data_audit_log SET
        action_details = '[Anonymized]'
    WHERE user_id = target_user_id;

    RAISE NOTICE 'User % data anonymized', target_user_id;
END;
$$ LANGUAGE plpgsql;

-- Grant necessary permissions
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO botuser;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO botuser;
