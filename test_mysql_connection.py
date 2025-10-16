"""
Script de test pour vérifier la connexion à la base de données MySQL
et la capacité d'écrire des configurations.
"""
import os
import json
from pathlib import Path
import mysql.connector
from mysql.connector import Error

# Paramètres de connexion depuis les variables d'environnement
DB_CONFIG = {
    'host': os.environ.get('MYSQL_HOST'),
    'user': os.environ.get('MYSQL_USER'),
    'password': os.environ.get('MYSQL_PASSWORD'),
    'database': os.environ.get('MYSQL_DATABASE'),
    'port': int(os.environ.get('MYSQL_PORT', 3306))
}

def test_connection():
    """Teste la connexion à la base de données."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            print("✅ Connexion à la base de données réussie")
            return conn
    except Error as e:
        print(f"❌ Erreur de connexion à la base de données: {e}")
        return None

def test_table_exists(conn):
    """Vérifie si la table app_config existe."""
    try:
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'app_config'")
        result = cursor.fetchone()
        if result:
            print("✅ Table 'app_config' trouvée")
            return True
        else:
            print("❌ Table 'app_config' non trouvée")
            return False
    except Error as e:
        print(f"❌ Erreur lors de la vérification de la table: {e}")
        return False

def test_insert_config(conn, key, value):
    """Teste l'insertion d'une configuration."""
    try:
        cursor = conn.cursor()
        # Vérifier si la clé existe déjà
        cursor.execute("SELECT config_value FROM app_config WHERE config_key = %s", (key,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"⚠️ La clé '{key}' existe déjà dans la base de données")
            return False
        
        # Insérer une nouvelle configuration
        cursor.execute(
            "INSERT INTO app_config (config_key, config_value) VALUES (%s, %s)",
            (key, json.dumps(value))
        )
        conn.commit()
        print(f"✅ Configuration '{key}' insérée avec succès")
        return True
        
    except Error as e:
        conn.rollback()
        print(f"❌ Erreur lors de l'insertion de la configuration: {e}")
        return False

def main():
    print("=== Test de connexion à la base de données ===")
    conn = test_connection()
    if not conn:
        return
    
    try:
        # Vérifier si la table existe
        if not test_table_exists(conn):
            print("\n⚠️ La table 'app_config' n'existe pas. Création...")
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_config (
                  config_key VARCHAR(191) PRIMARY KEY,
                  config_value JSON,
                  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            conn.commit()
            print("✅ Table 'app_config' créée avec succès")
        
        # Tester l'insertion d'une configuration
        test_config = {
            "test_key": "valeur_test",
            "timestamp": "2025-03-23T12:00:00Z"
        }
        test_insert_config(conn, "test_config", test_config)
        
    finally:
        if conn.is_connected():
            conn.close()
            print("\n✅ Connexion à la base de données fermée")

if __name__ == "__main__":
    main()
