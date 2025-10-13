<?php
/**
 * Database Logger
 * Handles database operations for logging Dropbox URLs
 */

class DatabaseLogger
{
    private $pdo;

    /**
     * Constructor - Initialize database connection
     */
    public function __construct()
    {
        $config = require dirname(__DIR__) . '/config/database.php';
        
        try {
            $dsn = "mysql:host={$config['host']};dbname={$config['database']};charset={$config['charset']}";
            $this->pdo = new PDO($dsn, $config['username'], $config['password'], $config['options']);
        } catch (PDOException $e) {
            error_log("Database connection failed: " . $e->getMessage());
            throw new Exception("Database connection failed");
        }
    }

    /**
     * Log a Dropbox URL to the database
     * 
     * @param string $url Processed Dropbox URL
     * @return bool True if logged successfully
     */
    public function logDropboxUrl($url)
    {
        if (empty($url)) {
            return false;
        }

        try {
            $sql = "INSERT INTO logs_dropbox (url_dropbox, timestamp) VALUES (?, ?)";
            $stmt = $this->pdo->prepare($sql);
            
            $timestamp = date('Y-m-d H:i:s');
            $result = $stmt->execute([$url, $timestamp]);
            
            if ($result) {
                error_log("Successfully logged Dropbox URL: " . $url);
                return true;
            }
            
            return false;
        } catch (PDOException $e) {
            error_log("Failed to log Dropbox URL: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Log multiple Dropbox URLs
     * 
     * @param array $urls Array of URLs to log
     * @return int Number of URLs successfully logged
     */
    public function logMultipleDropboxUrls($urls)
    {
        $successCount = 0;
        
        foreach ($urls as $url) {
            if ($this->logDropboxUrl($url)) {
                $successCount++;
            }
        }
        
        return $successCount;
    }

    /**
     * Get recent Dropbox URL logs
     * 
     * @param int $limit Number of records to retrieve
     * @return array Array of log records
     */
    public function getRecentLogs($limit = 50)
    {
        try {
            $sql = "SELECT * FROM logs_dropbox ORDER BY timestamp DESC LIMIT ?";
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute([$limit]);
            
            return $stmt->fetchAll();
        } catch (PDOException $e) {
            error_log("Failed to retrieve logs: " . $e->getMessage());
            return [];
        }
    }

    /**
     * Check if logs_dropbox table exists and create if not
     * 
     * @return bool True if table exists or was created successfully
     */
    public function ensureTableExists()
    {
        try {
            // Check if table exists
            $sql = "SHOW TABLES LIKE 'logs_dropbox'";
            $stmt = $this->pdo->query($sql);
            
            if ($stmt->rowCount() > 0) {
                return true; // Table already exists
            }
            
            // Create table
            $createSql = "
                CREATE TABLE logs_dropbox (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    url_dropbox TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            ";
            
            $this->pdo->exec($createSql);
            error_log("Created logs_dropbox table successfully");
            return true;
            
        } catch (PDOException $e) {
            error_log("Failed to ensure table exists: " . $e->getMessage());
            return false;
        }
    }

    /**
     * Get database connection for advanced operations
     * 
     * @return PDO Database connection
     */
    public function getConnection()
    {
        return $this->pdo;
    }
}
