-- Add new columns to oauth_accounts table for storing detailed third-party account info
ALTER TABLE oauth_accounts ADD COLUMN provider_email TEXT;
ALTER TABLE oauth_accounts ADD COLUMN provider_name TEXT;
ALTER TABLE oauth_accounts ADD COLUMN provider_avatar_url TEXT;
ALTER TABLE oauth_accounts ADD COLUMN access_token_expires_at TEXT;
ALTER TABLE oauth_accounts ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;
