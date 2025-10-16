"""
Script de migration des configurations JSON vers MySQL.
Migre les données depuis debug/processing_prefs.json et debug/webhook_config.json
vers la table app_config dans MySQL.
"""
import json
import os
from pathlib import Path
import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """Établit une connexion à la base de données MySQL."""
    try:
        connection = mysql.connector.connect(
            host='kidpixel.fr',
            database='kidp0_configs_render',
            user='kidp0_configs_render',
            password='ePeKnLEJEawjwSvryRt6',
            port=3306
        )
        return connection
    except Error as e:
        print(f"Erreur de connexion à la base de données: {e}")
        return None

def migrate_json_to_mysql():
    """Migre les données des fichiers JSON vers MySQL."""
    # Chemins des fichiers de configuration
    base_dir = Path(__file__).parent
    processing_prefs_path = base_dir / 'debug' / 'processing_prefs.json'
    webhook_config_path = base_dir / 'debug' / 'webhook_config.json'
    
    # Lire les données des fichiers JSON
    try:
        with open(processing_prefs_path, 'r') as f:
            processing_prefs = json.load(f)
        print("✅ Fichier processing_prefs.json chargé avec succès")
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de processing_prefs.json: {e}")
        return
    
    try:
        with open(webhook_config_path, 'r') as f:
            webhook_config = json.load(f)
        print("✅ Fichier webhook_config.json chargé avec succès")
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de webhook_config.json: {e}")
        return
    
    # Se connecter à la base de données
    connection = get_db_connection()
    if not connection:
        print("❌ Impossible de se connecter à la base de données")
        return
    
    cursor = None
    try:
        cursor = connection.cursor()
        
        # Vérifier/créer la table app_config si elle n'existe pas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                config_key VARCHAR(255) PRIMARY KEY,
                config_value JSON,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
                          ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
        
        # Migrer les préférences de traitement
        cursor.execute(
            """
            INSERT INTO app_config (config_key, config_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE 
                config_value = VALUES(config_value),
                updated_at = CURRENT_TIMESTAMP
            """,
            ('processing_prefs', json.dumps(processing_prefs, ensure_ascii=False))
        )
        
        # Migrer la configuration des webhooks
        cursor.execute(
            """
            INSERT INTO app_config (config_key, config_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE 
                config_value = VALUES(config_value),
                updated_at = CURRENT_TIMESTAMP
            """,
            ('webhook_config', json.dumps(webhook_config, ensure_ascii=False))
        )
        
        # Valider les changements
        connection.commit()
        
        # Vérifier que les données ont été correctement insérées
        cursor.execute("SELECT config_key FROM app_config")
        migrated_keys = [row[0] for row in cursor.fetchall()]
        
        print("\n✅ Migration terminée avec succès!")
        print(f"Clés migrées: {', '.join(migrated_keys)}")
        
        # Afficher un aperçu des données migrées
        print("\nAperçu des données migrées:")
        cursor.execute("SELECT config_key, JSON_PRETTY(config_value) FROM app_config")
        for key, value in cursor:
            print(f"\n--- {key} ---")
            print(value)
        
    except Error as e:
        print(f"❌ Erreur lors de la migration: {e}")
        if connection:
            connection.rollback()
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            print("\n✅ Connexion à la base de données fermée")

if __name__ == "__main__":
    print("Début de la migration des configurations vers MySQL...\n")
    migrate_json_to_mysql()
