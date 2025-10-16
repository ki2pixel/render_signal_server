"""
Script pour vérifier le contenu de la table app_config dans MySQL.
"""
import mysql.connector
from mysql.connector import Error
import json

def check_configs():
    try:
        # Paramètres de connexion
        connection = mysql.connector.connect(
            host='kidpixel.fr',
            database='kidp0_configs_render',
            user='kidp0_configs_render',
            password='ePeKnLEJEawjwSvryRt6',
            port=3306
        )

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # Vérifier les clés de configuration
            cursor.execute("SELECT config_key, LENGTH(config_value) as size, updated_at FROM app_config")
            configs = cursor.fetchall()
            
            print("Configurations trouvées dans la table app_config:")
            for cfg in configs:
                print(f"\n- {cfg['config_key']} (taille: {cfg['size']} octets, mis à jour: {cfg['updated_at']}")
                
                # Afficher un aperçu du contenu pour les clés connues
                if cfg['config_key'] in ['webhook_config', 'processing_prefs']:
                    cursor.execute("SELECT config_value FROM app_config WHERE config_key = %s", (cfg['config_key'],))
                    value = cursor.fetchone()['config_value']
                    try:
                        parsed = json.loads(value)
                        print(f"  Contenu: {json.dumps(parsed, indent=2, ensure_ascii=False)[:200]}...")
                    except json.JSONDecodeError:
                        print("  (contenu non-JSON)")

    except Error as e:
        print(f"Erreur de connexion à la base de données: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
            print("\nConnexion à la base de données fermée.")

if __name__ == "__main__":
    check_configs()
