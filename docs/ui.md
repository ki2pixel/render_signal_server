# Interface utilisateur (Dashboard Webhooks)

- Template: `dashboard.html`
- Script: `static/dashboard.js`

## Vue d'ensemble

Le dashboard a été refactorisé pour se concentrer exclusivement sur la gestion et le contrôle des webhooks, avec une navigation par onglets pour améliorer l'ergonomie. Les onglets incluent: Vue d'ensemble, Webhooks, Make, Préférences, Outils. Les anciennes fonctionnalités de télécommande à distance (déclenchement de workflow local) ont été supprimées. Migration de `trigger_page.html` vers `dashboard.html`.

## Sections du Dashboard

### 1. Fenêtre Horaire Globale

- **Inputs**: `#webhooksTimeStart`, `#webhooksTimeEnd`
- **Bouton**: `#saveTimeWindowBtn`
- **Message**: `#timeWindowMsg`
- **Appels API**:
  - `GET /api/get_webhook_time_window` pour charger les valeurs actuelles
  - `POST /api/set_webhook_time_window` pour sauvegarder
- **Formats acceptés**: `HHhMM`, `HH:MM`, `HHh`, `HH` (normalisés en `HHhMM`)
- **Comportement**: Laisser les deux champs vides désactive la contrainte horaire
- **Persistance**: `debug/webhook_time_window.json`
- **Effet**: Immédiat, sans redéploiement

### 2. Préférences Make (Polling IMAP)

#### 2.a Configuration du Polling (jours, heures, déduplication)

- **Jours actifs**: cases à cocher `#pollingActiveDaysGroup` (7 cases, valeurs `0..6` correspondant à `Mon..Sun`)
  - Cette interface remplace l'ancien champ texte `POLLING_ACTIVE_DAYS`
  - La sélection est envoyée au backend comme liste d'indices, ex: `[0,1,2,3,4]`
- **Heures actives**:
  - Début: `#pollingStartHour` (nombre 0-23)
  - Fin: `#pollingEndHour` (nombre 0-23)
- **Déduplication par groupe de sujet**: toggle `#enableSubjectGroupDedup`
- **Expéditeurs surveillés**:
  - Conteneur: `#senderOfInterestContainer`
  - Bouton d'ajout: `#addSenderBtn` (inputs email individuels avec bouton « ❌ » par ligne)
  - Validation côté client: normalisation lowercase, regex email, déduplication

**Appels API**:
- `GET /api/get_polling_config` pour charger la configuration polling (jours, heures, expéditeurs, dédup)
- `POST /api/update_polling_config` pour sauvegarder les modifications

**Comportement**:
- Les jours actifs sont désormais gérés exclusivement via cases à cocher; l'ancienne saisie texte n'est plus utilisée.
- Un redémarrage du serveur peut être nécessaire pour appliquer totalement certains changements selon l'environnement.

**Persistance**: `debug/polling_config.json`

**Note**: L'onglet 'Make' permet uniquement la configuration manuelle des préférences de polling IMAP. Le contrôle automatisé des scénarios Make.com a été supprimé.

### 3. Configuration des URLs Webhooks

Permet de configurer l'URL de webhook principale et les options associées :

- **Webhook personnalisé (obligatoire)**: `#webhookUrl` (WEBHOOK_URL)
- **Flag PRESENCE** (contrôle le comportement le samedi) : `#presenceFlag` (select true/false)
- **Vérification SSL** (active/désactive la vérification des certificats) : `#sslVerifyToggle` (WEBHOOK_SSL_VERIFY)

**Note** : Les webhooks spécifiques à Make.com (Recadrage, Autorépondeur, Présence) ont été dépréciés. Tous les appels sont maintenant dirigés vers l'URL de webhook principale configurée ci-dessus.

**Appels API**:
- `GET /api/get_webhook_config` pour charger la configuration actuelle (URLs masquées partiellement)
- `POST /api/update_webhook_config` pour sauvegarder les modifications

**Sécurité**:
- Les URLs sont masquées partiellement lors de l'affichage pour la sécurité
- Seules les URLs complètes saisies sont envoyées au backend
- Validation côté serveur (format HTTPS, normalisation des tokens Make.com)

**Persistance**: `debug/webhook_config.json`

### 4. Historique des Webhooks

- **Container**: `#logsContainer`
- **Bouton refresh**: `#refreshLogsBtn`
- **Appel API**: `GET /api/webhook_logs?days=7`
- **Auto-refresh**: Toutes les 30 secondes
- **Affichage**: Max 50 entrées les plus récentes
- **Filtrage**: 7 derniers jours par défaut

**Format des entrées de log**:
- Timestamp (format local FR)
- Type de webhook (CUSTOM ou MAKE.COM)
- Statut (✅ Succès ou ❌ Erreur)
- Sujet de l'email (tronqué à 100 caractères)
- URL cible (masquée partiellement)
- Code HTTP
- Message d'erreur si applicable
- Email ID

**Codes couleur**:
- Bordure verte: Succès
- Bordure rouge: Erreur
- Badge bleu: Webhook custom
- Badge orange: Webhook Make.com

### 5. Préférences de Traitement (serveur)

- Champs UI:
  - `#excludeKeywords` (textarea, un mot-clé par ligne)
  - `#attachmentDetectionToggle` (checkbox)
  - `#maxEmailSizeMB` (number)
  - `#senderPriority` (textarea JSON simple)
  - `#retryCount`, `#retryDelaySec`, `#webhookTimeoutSec`, `#rateLimitPerHour` (numbers)
  - `#notifyOnFailureToggle` (checkbox)
  - Bouton: `#processingPrefsSaveBtn`
- API:
  - `GET /api/get_processing_prefs` (chargement)
  - `POST /api/update_processing_prefs` (sauvegarde)
- Normalisation côté serveur: types (bool/int), JSON valide pour `sender_priority`, valeurs par défaut raisonnables.

### 6. Gestion des Configurations (Export/Import)

- Boutons: `#exportConfigBtn`, `#importConfigBtn` + input fichier `#importConfigFile`
- Export regroupe:
  - `GET /api/get_webhook_config`, `GET /api/get_polling_config`, `GET /api/get_webhook_time_window`
  - Préférences UI locales (localStorage)
- Import applique automatiquement:
  - `POST /api/update_webhook_config`
  - `POST /api/update_polling_config`
  - `POST /api/set_webhook_time_window`
- Notes: les champs non supportés sont ignorés; certaines mises à jour peuvent nécessiter un redémarrage.

### 7. Outils de Test (client)

- Validation d'URL Make.com ou alias: input `#testWebhookUrl` + bouton `#validateWebhookUrlBtn`
- Génération d'un payload d'aperçu: `#previewSubject`, `#previewSender`, `#previewBody` + `#buildPayloadPreviewBtn`
- Règles:
  - URLs Make.com acceptent `https://hook.euX.make.com/<token>` ou alias `<token>@hook.euX.make.com`
  - Les URLs HTTPS génériques sont aussi vérifiées pour le format

### 8. Monitoring & Métriques

- Toggle: `#enableMetricsToggle`
- Indicateurs: `#metricEmailsProcessed`, `#metricWebhooksSent`, `#metricErrors`, `#metricSuccessRate`
- Mini-graph: `#metricsMiniChart`
- Source: `GET /api/webhook_logs?days=1`
- Calcul côté client (approximation à partir des logs récents)

## Conventions JavaScript

### Structure du code

Le fichier `dashboard.js` est organisé en sections correspondant aux 4 fonctionnalités principales:
1. Utilitaires (`showMessage`, `formatTimestamp`, `escapeHtml`)
2. Fenêtre horaire (`loadTimeWindow`, `saveTimeWindow`)
3. Contrôle polling (`loadPollingStatus`, `togglePolling`)
4. Configuration webhooks (`loadWebhookConfig`, `saveWebhookConfig`)
5. Logs webhooks (`loadWebhookLogs`)

### Initialisation

Au chargement de la page (`DOMContentLoaded`):
1. Chargement initial de toutes les données
2. Attachement des gestionnaires d'événements
3. Démarrage de l'auto-refresh des logs (30s)

### Gestion des messages

Fonction utilitaire `showMessage(elementId, message, type)`:
- Types: `success`, `error`, `info`
- Auto-disparition après 5 secondes
- Styles visuels cohérents avec le thème Cork

## Thème et Design

Le dashboard utilise le thème Cork (dark mode) avec les variables CSS:
- Couleurs principales définies dans `:root`
- Layout responsive avec CSS Grid
- Cards pour chaque section
- Animations subtiles sur les boutons
- Toggle switches modernes pour les booléens

### Contrôles de la liste d'expéditeurs (thème sombre)

- Les boutons « ➕ Ajouter Email » (`#addSenderBtn`) et « ❌ » (classe `.email-remove-btn`) adoptent un style sombre cohérent:
  - Fond `var(--cork-card-bg)`, bordure `var(--cork-border-color)`, texte `var(--cork-text-primary)`
  - Hover: `#addSenderBtn` → `var(--cork-primary-accent)`; `.email-remove-btn` → `var(--cork-danger)`
- Accessibilité: ajout d'un `title` descriptif sur le bouton « ❌ » via `dashboard.js`.

## Migration depuis l'ancienne télécommande

**Fonctionnalités supprimées**:
- Bouton "Lancer Séquence Locale"
- Bouton "Vérifier Emails & Transférer"
- Polling du statut du worker local
- Affichage de la progression des téléchargements
- Scripts `ui.js`, `api.js`, `main.js` (non utilisés)

## 9. Flags Runtime (Debug) - Onglet Outils

- **Toggles**: `#disableEmailIdDedupToggle`, `#allowCustomWebhookWithoutLinksToggle`
- **Bouton**: `#saveRuntimeFlagsBtn`
- **Message**: `#runtimeFlagsMsg`
- **Appels API**:
  - `GET /api/get_runtime_flags` pour charger les flags actuels
  - `POST /api/update_runtime_flags` pour sauvegarder
- **Persistance**: `debug/runtime_flags.json`
- **Effet**: Immédiat, contrôle dynamique du bypass déduplication et envoi webhook sans liens

### 10. Outils - Onglet Outils

- **Outil "Ouvrir une page de téléchargement"**: permet d'ouvrir manuellement une URL de fournisseur (Dropbox/FromSmash/SwissTransfer) dans un nouvel onglet.
- **Simplification de la gestion des liens**: remplace la logique d'extraction automatique de liens directs, désormais supprimée pour stabilité.

### 11. Déploiement de l'application - Onglet Outils

- **Bouton**: `#restartServerBtn` (libellé: « 🚀 Déployer l'application »)
- **Message**: `#restartServerMsg`
- **Appel API**: `POST /api/deploy_application`
- **Comportement**: confirmation utilisateur, lancement du déploiement côté serveur puis vérification de disponibilité via `/health` avant rechargement automatique de la page.
- **Gestion erreurs**: Messages d'erreur si échec de la commande ou si le service n'est pas encore disponible après un nombre d'essais.

**Détails backend**:
- Endpoint: défini dans `routes/api_admin.py` (`deploy_application()`).
- Variable d'environnement: `DEPLOY_CMD` pour surcharger la commande par défaut.
- Commande par défaut:
  - `sudo systemctl reload-or-restart render-signal-server; sudo nginx -s reload || sudo systemctl reload nginx`
- Exécution asynchrone en arrière-plan (non bloquant).

**Health-check côté client**:
- Après succès d'`/api/deploy_application`, le front appelle périodiquement `GET /health` (10 tentatives max, intervalle ~1,5s). Au premier `200 OK`, la page est rechargée.
- Si les tentatives échouent, un message invite à recharger manuellement plus tard.

**Fonctionnalités conservées**:
- Fenêtre horaire des webhooks (étendue)
- Authentification Flask-Login
- Lien de déconnexion

**Nouveautés**:
- Contrôle complet des webhooks depuis l'UI
- Visualisation des logs en temps réel
- Toggle du polling IMAP
- Configuration dynamique sans redéploiement (pour certains paramètres)
 - Outil « Ouvrir une page de téléchargement »: permet d'ouvrir manuellement une URL de fournisseur (Dropbox/FromSmash/SwissTransfer) dans un nouvel onglet. Cet outil remplace la logique d'extraction automatique de liens directs, désormais supprimée pour stabilité.
