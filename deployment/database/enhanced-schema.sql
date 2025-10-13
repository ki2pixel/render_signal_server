-- Enhanced Database Schema (Optional)
-- Additional tables for monitoring and debugging
-- These are NOT required for Make.com compatibility

-- Table for webhook request logs
CREATE TABLE IF NOT EXISTS webhook_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    webhook_data JSON,
    sender_email VARCHAR(255),
    subject TEXT,
    received_datetime DATETIME,
    processing_status ENUM('success', 'failed', 'unauthorized') NOT NULL,
    error_message TEXT,
    processed_urls_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sender_email (sender_email),
    INDEX idx_processing_status (processing_status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table for email processing logs
CREATE TABLE IF NOT EXISTS email_processing_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sender_email VARCHAR(255),
    subject TEXT,
    search_criteria JSON,
    email_found BOOLEAN DEFAULT FALSE,
    dropbox_urls_found INT DEFAULT 0,
    processing_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sender_email (sender_email),
    INDEX idx_email_found (email_found),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table for system errors and debugging
CREATE TABLE IF NOT EXISTS system_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    log_level ENUM('info', 'warning', 'error', 'debug') NOT NULL,
    component VARCHAR(100),
    message TEXT NOT NULL,
    context JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_log_level (log_level),
    INDEX idx_component (component),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
