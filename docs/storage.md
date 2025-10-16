# Stockage de la configuration

## Architecture de stockage

L'application utilise une architecture de stockage hiérarchique pour la persistance des configurations :

1. **Backend JSON externe** (recommandé en production) - Nouveau système
2. **Fichiers locaux** (fallback pour le développement et compatibilité)
3. **MySQL** (déprécié, supprimé dans la version actuelle)

## Backend JSON externe

### Configuration requise

Pour activer le stockage externe, définissez ces variables d'environnement :

- `EXTERNAL_CONFIG_BASE_URL` : URL de base de l'API de configuration (ex: `https://votre-domaine.tld`)
- `CONFIG_API_TOKEN` : Jeton d'authentification pour l'API (doit correspondre à `CONFIG_API_TOKEN` dans `deployment/config/config_api.php`)

### Fichiers de configuration gérés

- **Webhooks** : Configuration des webhooks et fenêtres horaires
- **Préférences de traitement** : Règles de filtrage et de traitement des e-mails
- **Fenêtres horaires** : Configuration des plages d'exécution
- **Flags runtime** : Paramètres de débogage et fonctionnalités expérimentales

### Fonctionnement

1. **Ordre de priorité** :
   - L'application tente d'abord de se connecter au backend externe
   - En cas d'échec, elle utilise les fichiers locaux comme fallback
   - Une notification est journalisée en cas de basculement sur le mode fallback

2. **Mécanisme de cache** :
   - Les configurations sont mises en cache en mémoire après le premier chargement
   - Le cache est invalidé lors des opérations d'écriture
   - La synchronisation avec le stockage persistant est assurée automatiquement

3. **Sécurité** :
   - Authentification via token Bearer
   - Validation des données avant écriture
   - Chiffrement des données sensibles au repos (si configuré)

4. **Journalisation** :
   - Toutes les opérations de lecture/écriture sont journalisées
   - Les erreurs sont enregistrées avec un niveau de sévérité approprié

### Configuration du serveur PHP

1. Déployez les fichiers PHP dans votre hébergement web :
   - `deployment/public_html/config_api.php` → Point d'entrée de l'API
   - `deployment/config/config_api.php` → Configuration (à sécuriser hors du webroot)

2. Configurez le jeton d'API dans `deployment/config/config_api.php` :
   ```php
   define('CONFIG_API_TOKEN', 'votre_jeton_secret_ici');
   ```

3. Assurez-vous que le dossier de stockage est accessible en écriture par le serveur web :
   ```bash
   mkdir -p /chemin/vers/deployment/data/app_config
   chmod 775 /chemin/vers/deployment/data/app_config
   ```

## Fallback local

Si le backend externe n'est pas configuré ou n'est pas accessible, l'application utilise des fichiers JSON locaux dans le dossier `debug/` :

- `debug/webhook_config.json` - Configuration des webhooks
- `debug/processing_prefs.json` - Préférences de traitement
- `debug/webhook_time_window.json` - Fenêtres horaires des webhooks
- `debug/runtime_flags.json` - Paramètres d'exécution

### Comportement en mode fallback

- **Lecture** : Les fichiers locaux sont lus directement
- **Écriture** : Les modifications sont enregistrées dans les fichiers locaux
- **Synchronisation** : Aucune synchronisation automatique avec le backend externe n'est effectuée
- **Notification** : Un avertissement est affiché dans l'interface utilisateur


## Dépannage

### Erreurs courantes

#### Erreurs d'authentification
- **Symptômes** : Erreurs 401 Unauthorized dans les logs
- **Solutions** :
  - Vérifiez que `CONFIG_API_TOKEN` correspond entre l'application et `deployment/config/config_api.php`
  - Vérifiez que le header `Authorization: Bearer` est correctement envoyé
  - Assurez-vous que l'horloge du serveur est synchronisée (NTP)

#### Problèmes de permissions
- **Symptômes** : Erreurs 500 ou échec d'écriture
- **Solutions** :
  - Vérifiez les permissions du dossier de stockage : `chmod 775 /chemin/vers/donnees`
  - Vérifiez le propriétaire des fichiers : `chown www-data:www-data /chemin/vers/donnees/*`
  - Consultez les logs d'erreurs PHP pour plus de détails

#### Problèmes de performance
- **Symptômes** : Lenteur du chargement de la configuration
- **Solutions** :
  - Activez le cache OPcache pour PHP
  - Vérifiez la latence réseau vers le serveur de configuration
  - Considérez l'utilisation d'un CDN pour les fichiers statiques

### Surveillance

#### Métriques clés
- Temps de réponse du backend de configuration
- Taux d'erreurs (4xx, 5xx)
- Taux d'utilisation du cache
- Fréquence des basculements en mode fallback

#### Alertes recommandées
- Plus de 3 échecs consécutifs du backend externe
- Temps de réponse > 1 seconde
- Taux d'erreur > 1% sur 5 minutes
- Utilisation du disque > 80% sur le volume de stockage

## Référence de l'API

### Lecture d'une configuration

```bash
curl -H "Authorization: Bearer VOTRE_TOKEN" \
  "https://votre-domaine.tld/config_api.php?key=webhook_config"
```

**Paramètres** :
- `key` (obligatoire) : Clé de configuration à récupérer (ex: `webhook_config`, `processing_prefs`)

**Réponse** :
```json
{
  "status": "success",
  "data": {
    "webhook_url": "https://exemple.com/webhook",
    "webhook_enabled": true,
    "time_window": {
      "start_hour": 8,
      "end_hour": 20,
      "active_days": [1, 2, 3, 4, 5]
    }
  },
  "timestamp": "2025-10-16T14:30:00Z"
}
```

### Écriture d'une configuration

```bash
curl -X POST \
  -H "Authorization: Bearer VOTRE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "webhook_config",
    "config": {
      "webhook_url": "https://exemple.com/webhook",
      "webhook_enabled": true,
      "time_window": {
        "start_hour": 8,
        "end_hour": 20,
        "active_days": [1, 2, 3, 4, 5]
      }
    }
  }' \
  "https://votre-domaine.tld/config_api.php"
```

**Corps de la requête** :
- `key` (obligatoire) : Clé de configuration à mettre à jour
- `config` (obligatoire) : Objet de configuration complet

**Réponse** :
```json
{
  "status": "success",
  "message": "Configuration mise à jour avec succès",
  "timestamp": "2025-10-16T14:35:00Z"
}
```

### Codes d'erreur

| Code HTTP | Description |
|-----------|-------------|
| 200 | Succès |
| 400 | Requête invalide (paramètres manquants ou invalides) |
| 401 | Non autorisé (token invalide ou manquant) |
| 403 | Accès refusé (permissions insuffisantes) |
| 404 | Clé de configuration non trouvée |
| 500 | Erreur interne du serveur |

## Bonnes pratiques

1. **Sécurité** :
   - Utilisez toujours HTTPS pour les connexions au backend
   - Limitez l'accès à l'API par adresse IP si possible
   - Changez régulièrement les jetons d'API
   - Ne stockez jamais de jetons dans le code source

2. **Sauvegarde** :
   - Mettez en place des sauvegardes régulières des fichiers de configuration
   - Conservez un historique des modifications
   - Testez régulièrement la restauration des sauvegardes
