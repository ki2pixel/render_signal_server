"""
Script de test final pour vérifier la connexion MySQL avec les bonnes informations.
"""
import mysql.connector
from mysql.connector import Error
import json

def test_connection():
    """Teste la connexion à la base de données MySQL avec les bonnes informations."""
    try:
        # Paramètres de connexion mis à jour
        connection_params = {
            'host': 'kidpixel.fr',
            'database': 'kidp0_configs_render',
            'user': 'kidp0_configs_render',
            'password': 'ePeKnLEJEawjwSvryRt6',
            'port': 3306,
            'use_pure': True
        }
        
        print("Tentative de connexion à la base de données avec les paramètres suivants:")
        print(f"- Hôte: {connection_params['host']}")
        print(f"- Base de données: {connection_params['database']}")
        print(f"- Utilisateur: {connection_params['user']}")
        
        # Tenter la connexion
        connection = mysql.connector.connect(**connection_params)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"\n✅ Connexion réussie à MySQL Server version {db_info}")
            
            cursor = connection.cursor()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()[0]
            print(f"✅ Connecté à la base de données: {db_name}")
            
            # Vérifier/créer la table app_config
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_config (
                    config_key VARCHAR(255) PRIMARY KEY,
                    config_value JSON,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
                              ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
            print("✅ Table 'app_config' vérifiée/créée")
            
            # Tester une insertion
            test_key = "test_connection"
            test_value = {"status": "success", "message": "Test de connexion réussi"}
            
            cursor.execute("""
                INSERT INTO app_config (config_key, config_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE 
                    config_value = VALUES(config_value),
                    updated_at = CURRENT_TIMESTAMP
            """, (test_key, json.dumps(test_value)))
            
            connection.commit()
            print("✅ Données de test insérées avec succès")
            
            # Vérifier la lecture
            cursor.execute("""
                SELECT config_value, updated_at 
                FROM app_config 
                WHERE config_key = %s
            """, (test_key,))
            
            result = cursor.fetchone()
            if result:
                print("\n✅ Lecture des données réussie:")
                print(f"- Valeur: {result[0]}")
                print(f"- Dernière mise à jour: {result[1]}")
            
            # Nettoyage
            cursor.execute("DELETE FROM app_config WHERE config_key = %s", (test_key,))
            connection.commit()
            
    except Error as e:
        print(f"\n❌ Erreur lors de la connexion à MySQL: {e}")
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            print("\n✅ Connexion MySQL fermée")

if __name__ == "__main__":
    test_connection()
