-- Database initialization script for find-brilliant
-- Creates tables for users, search requests, keywords, and groups

-- Enable UUID extension (optional, for future use)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop tables if they exist (for clean re-initialization)
DROP TABLE IF EXISTS search_request_groups CASCADE;
DROP TABLE IF EXISTS search_request_keywords CASCADE;
DROP TABLE IF EXISTS search_requests CASCADE;
DROP TABLE IF EXISTS telegram_groups CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. Users table
-- Stores Telegram users who create search requests
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookup by telegram_id
CREATE INDEX idx_users_telegram_id ON users(telegram_id);

-- 2. Telegram groups table
-- Stores unique Telegram groups/channels (shared across all search requests)
CREATE TABLE telegram_groups (
    telegram_group_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    title VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookup by username
CREATE INDEX idx_telegram_groups_username ON telegram_groups(username);

-- 3. Search requests table
-- Represents one logical search request created by a user
CREATE TABLE search_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster lookup by user_id and active status
CREATE INDEX idx_search_requests_user_id ON search_requests(user_id);
CREATE INDEX idx_search_requests_is_active ON search_requests(is_active);
CREATE INDEX idx_search_requests_user_active ON search_requests(user_id, is_active);

-- 4. Search request keywords table
-- Stores keywords belonging to a specific search request
-- Keywords are normalized to lowercase
CREATE TABLE search_request_keywords (
    id SERIAL PRIMARY KEY,
    search_request_id INTEGER NOT NULL REFERENCES search_requests(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL
);

-- Index for faster lookup by search_request_id
CREATE INDEX idx_search_request_keywords_request_id ON search_request_keywords(search_request_id);
-- Index for keyword searches
CREATE INDEX idx_search_request_keywords_keyword ON search_request_keywords(keyword);

-- 5. Search request groups table (junction table)
-- Links search requests to telegram groups (many-to-many relationship)
-- Same Telegram group can be used in multiple search requests
CREATE TABLE search_request_groups (
    id SERIAL PRIMARY KEY,
    search_request_id INTEGER NOT NULL REFERENCES search_requests(id) ON DELETE CASCADE,
    telegram_group_id BIGINT NOT NULL REFERENCES telegram_groups(telegram_group_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Ensure a group can't be added twice to the same search request
    UNIQUE(search_request_id, telegram_group_id)
);

-- Index for faster lookup by search_request_id
CREATE INDEX idx_search_request_groups_request_id ON search_request_groups(search_request_id);
-- Index for faster lookup by telegram_group_id
CREATE INDEX idx_search_request_groups_telegram_id ON search_request_groups(telegram_group_id);

-- Comments for documentation
COMMENT ON TABLE users IS 'Stores Telegram users who create search requests';
COMMENT ON TABLE telegram_groups IS 'Stores unique Telegram groups/channels (shared across all users and requests)';
COMMENT ON TABLE search_requests IS 'Main entity representing a search request that can be listed, paused, or deleted';
COMMENT ON TABLE search_request_keywords IS 'Keywords for each search request (not shared between requests)';
COMMENT ON TABLE search_request_groups IS 'Junction table linking search requests to telegram groups (many-to-many)';

COMMENT ON COLUMN users.telegram_id IS 'Telegram user ID (unique)';
COMMENT ON COLUMN telegram_groups.telegram_group_id IS 'Telegram group/channel ID (unique across all groups)';
COMMENT ON COLUMN search_requests.is_active IS 'Whether this search request is currently enabled';
COMMENT ON COLUMN search_request_keywords.keyword IS 'Raw keyword text (normalized to lowercase)';
COMMENT ON COLUMN search_request_groups.telegram_group_id IS 'Reference to telegram_groups table';

