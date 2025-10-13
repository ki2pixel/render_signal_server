-- Database Schema for Dropbox URL Processor
-- EXACT REPLICA of Make.com scenario database structure
--
-- This table structure MUST match the original Make.com automation exactly
-- Original Make.com SQL: INSERT INTO logs_dropbox (url_dropbox, timestamp) VALUES (...)

-- Create the logs_dropbox table (EXACT Make.com blueprint structure)
CREATE TABLE IF NOT EXISTS logs_dropbox (
    id INT AUTO_INCREMENT PRIMARY KEY,
    url_dropbox TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add indexes for performance (optional, doesn't affect compatibility)
CREATE INDEX IF NOT EXISTS idx_timestamp ON logs_dropbox (timestamp);
CREATE INDEX IF NOT EXISTS idx_created_at ON logs_dropbox (created_at);
