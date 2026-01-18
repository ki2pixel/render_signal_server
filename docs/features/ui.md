- ## Contrôles post-déploiement (Render)
-
- Après chaque déploiement (via GHCR → Render ou `/api/deploy_application`), vérifier rapidement depuis le dashboard :
- - Connexion `/login` et navigation entre les onglets (veille que les assets statiques sont bien servis par l’image Docker).
- - Chargement des sections critiques :
-   - **Vue Webhooks** : `GET /api/webhooks/config` reflète les valeurs Render (URL masquée, absence globale).
-   - **Fenêtre horaire** : vérifier que les champs se remplissent correctement (`GET /api/webhooks/time-window`).
-   - **Poller** : l’onglet Polling doit afficher l’état `enable_polling` et les jours/heures attendus.
- - Si un échec Render est suspecté, consulter l’onglet “Administration” (API admin) pour déclencher `/api/deploy_application` en fallback.
- - Surveiller les bandes d’alertes UI (toasts) : toute erreur d’API post-déploiement doit être investiguée (logs Render, onglet Logs).

# Interface utilisateur (Dashboard Webhooks) - Architecture Orientée Services

- **Template principal**: `dashboard.html`
- **Script principal**: `static/dashboard.js`
- **Architecture**: Interface utilisant des services backend via des appels API REST

## Vue d'ensemble

Le dashboard a été refactorisé pour utiliser une architecture orientée services, avec une séparation claire entre l'interface utilisateur et la logique métier. Les principales caractéristiques sont :

- **Navigation par onglets** : Vue d'ensemble, Webhooks, Configuration, Outils
- **Authentification** : Gérée par `AuthService`
- **Configuration** : Gérée par `ConfigService` et `WebhookConfigService`
- **Déduplication** : Gérée par `DeduplicationService` (Redis ou mémoire)
- **Polling** : Géré par `PollingConfigService`

## Intégration avec les services

L'interface communique avec les services backend via des appels API REST. Les principaux services utilisés sont :

- `WebhookConfigService` : Configuration des webhooks
- `RuntimeFlagsService` : Gestion des flags de runtime
- `PollingConfigService` : Configuration du polling IMAP
- `DeduplicationService` : Gestion de la déduplication
- `AuthService` : Authentification et autorisation
- `MagicLinkService` : Génération et validation des magic links

## Authentification par Magic Links (2026-01-08)

### Vue d'ensemble

Le dashboard supporte désormais l'authentification par magic links pour simplifier l'accès admin récurrent :

- **Génération de liens** : Via l'interface `/login` (bouton "Générer un Magic Link")
- **Modes supportés** : 
  - One-shot (TTL configurable, usage unique)
  - Permanent (illimité, révocation manuelle)
- **Stockage sécurisé** : Tokens signés HMAC-SHA256 avec `FLASK_SECRET_KEY`
- **Interface utilisateur** : Champ token sur la page de login, bouton copie automatique

### Flux utilisateur

1. **Génération** (admin connecté) :
   - Accéder à `/login` → bouton "Générer un Magic Link"
   - Cocher "Illimité" pour un lien permanent
   - Copier automatiquement le lien généré

2. **Utilisation** :
   - Visiter l'URL du magic link (redirection automatique)
   - Ou saisir manuellement le token dans le champ "Magic Token" sur `/login`
   - Authentification automatique si le token est valide

3. **Sécurité** :
   - Tokens one-shot expirés après utilisation
   - Tokens permanents stockés dans `MAGIC_LINK_TOKENS_FILE`
   - Nettoyage automatique des tokens expirés

### Configuration

Variables d'environnement :
```bash
MAGIC_LINK_TTL_SECONDS=3600    # TTL pour les tokens one-shot (1h par défaut)
MAGIC_LINK_TOKENS_FILE=/app/data/magic_links.json
FLASK_SECRET_KEY=votre-clé-secrète-robuste  # Requis pour la signature
EXTERNAL_CONFIG_BASE_URL=webhook.kidpixel.fr   # Active le store partagé
CONFIG_API_TOKEN=token-ultra-secret                  # Jeton HMAC pour l'API PHP
CONFIG_API_STORAGE_DIR=/home/kidp0/.../data/app_config # Emplacement serveur PHP
```

Lorsque `EXTERNAL_CONFIG_BASE_URL` + `CONFIG_API_TOKEN` sont définis, `MagicLinkService`
stocke les tokens permanents dans l’API PHP (`deployment/config/config_api.php`) qui
écrit sous `CONFIG_API_STORAGE_DIR`. Le fallback fichier JSON local reste utilisé si
l’API est indisponible (ex: maintenance du serveur PHP ou variable manquante). Ce
fonctionnement partagé garantit que les tokes illimités survivent aux redéploiements
Render multi-workers.

### API

- `POST /api/auth/magic-link` : Générer un nouveau magic link (protégé par session)
- `GET /login/magic/<token>` : Consommer un magic link (redirection automatique)

### Logs

Les événements sont loggés avec le préfixe `MAGIC_LINK` :
```
MAGIC_LINK: token generated (expires_at=2026-01-08T14:30:00Z)
MAGIC_LINK: token abc123 consommé par admin_user
```

## Sections du Dashboard

### 1. Fenêtre Horaire Globale

- **Inputs**: `#webhooksTimeStart`, `#webhooksTimeEnd`
- **Bouton**: `#saveTimeWindowBtn`
- **Message**: `#timeWindowMsg`
- **Appels API**:
  - Recommandé: `GET /api/webhooks/time-window` pour charger, `POST /api/webhooks/time-window` pour sauvegarder
  - Legacy (compat): `GET /api/get_webhook_time_window`, `POST /api/set_webhook_time_window`
- **Formats acceptés**: `HHhMM`, `HH:MM`, `HHh`, `HH` (normalisés en `HHhMM`)
- **Comportement**: Laisser les deux champs vides désactive la contrainte horaire
- **Persistance**: via `WebhookConfigService` (store externe prioritaire, fallback fichier `debug/webhook_config.json`)
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
- **Envoi des webhooks** (activation/désactivation globale) : `#webhookSendingToggle` (WEBHOOK_SENDING_ENABLED)
- **Vérification SSL** (active/désactive la vérification des certificats) : `#sslVerifyToggle` (WEBHOOK_SSL_VERIFY)
- **Absence Globale (Stop Emails)** : toggle `#absencePauseToggle` + cases `#absencePauseDaysGroup`

**Note** : Les webhooks spécifiques à Make.com (Recadrage, Autorépondeur, Présence) ont été dépréciés. Tous les flux passent désormais par l'URL de webhook principale configurée ci-dessus.

**Appels API**:
- Recommandé: `GET /api/webhooks/config` pour charger, `POST /api/webhooks/config` pour sauvegarder (URL masquée côté lecture)
- Legacy (compat): `GET /api/get_webhook_config`, `POST /api/update_webhook_config`

**Sécurité**:
- Les URLs sont masquées partiellement lors de l'affichage pour la sécurité
- Seules les URLs complètes saisies sont envoyées au backend
- Validation côté serveur (format HTTPS, normalisation des tokens Make.com)
- Les jours sélectionnés pour l'absence sont normalisés côté serveur (`strip()` + `lower()`), et au moins un jour est requis pour activer la pause

**Persistance**: `debug/webhook_config.json`

#### Absence Globale (Stop Emails)

- **Effet immédiat** : dès qu'un jour configuré correspond au jour courant, `check_new_emails_and_trigger_webhook()` loggue `ABSENCE_PAUSE` et termine le cycle avant toute connexion IMAP (aucun webhook envoyé).
- **Validation UI** : l'interface empêche l'enregistrement si aucun jour n'est coché lorsque le toggle est actif (message d'erreur + accent orange).
- **Synchronisation automatique** : rechargement des cases à cocher après sauvegarde, en cohérence avec la normalisation côté backend (jours toujours affichés en minuscules).

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

## 10. Sécurité et Accès

### 10.1 Accès par Magic Link

La section "Accès Magic Link" permet de générer des liens d'authentification sécurisés pour accéder au tableau de bord sans identifiants.

#### Fonctionnalités

- **Génération de liens** : Crée des liens d'accès temporaires ou permanents
- **Deux modes d'utilisation** :
  - **Lien à usage unique** : Expire après utilisation (par défaut)
  - **Lien permanent** : Reste actif jusqu'à révocation manuelle
- **Sécurité** :
  - Chaque lien est signé avec HMAC-SHA256
  - Les liens à usage unique sont automatiquement invalidés après utilisation
  - Les liens expirés sont automatiquement nettoyés
  - Les liens peuvent être révoqués à tout moment

#### Interface Utilisateur

- **Bouton de génération** : "✨ Générer un magic link"
- **Option "Mode illimité"** : Permet de basculer entre les liens à usage unique et permanents
- **Zone d'affichage** : Affiche le lien généré avec son statut d'expiration
- **Copie automatique** : Le lien est automatiquement copié dans le presse-papiers

#### Comportement

1. **Génération** :
   - Cliquer sur "Générer un magic link"
   - Le lien est généré et affiché
   - Un message de confirmation s'affiche

2. **Utilisation** :
   - Ouvrir le lien dans un navigateur
   - Si valide, l'utilisateur est automatiquement connecté au tableau de bord
   - Pour les liens à usage unique, le lien est immédiatement invalidé après utilisation

3. **Expiration** :
   - Liens à usage unique : 15 minutes par défaut (configurable via `MAGIC_LINK_TTL_SECONDS`)
   - Liens permanents : Pas d'expiration, doivent être révoqués manuellement

#### Bonnes pratiques

- Ne partager les liens qu'avec des personnes autorisées
- Préférer les liens à usage unique pour un accès temporaire
- Révoquer immédiatement tout lien compromis
- Ne pas utiliser de liens permanents pour un accès de longue durée
- Vérifier régulièrement la liste des liens actifs

#### Dépannage

- **Lien expiré** : Générer un nouveau lien
- **Lien déjà utilisé** : Les liens à usage unique ne peuvent être utilisés qu'une seule fois
- **Erreur de signature** : Le lien a peut-être été altéré, générer un nouveau lien
- **Accès refusé** : Vérifier les autorisations de l'utilisateur

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

## Contrôles post-déploiement (Render)

Après chaque déploiement (pipeline GHCR → Render ou fallback `/api/deploy_application`), réaliser un “smoke test” rapide via le dashboard :

1. **Connexion UI** : accéder à `/login`, vérifier que les assets statiques de l’image Docker sont servis (CSS/JS chargés, onglets fonctionnels).
2. **Onglet Webhooks** : confirmer que `GET /api/webhooks/config` remonte les valeurs Render (URL masquée, absence globale cohérente).
3. **Fenêtre horaire** : ouvrir l’onglet dédié, vérifier que les champs se pré-remplissent (`GET /api/webhooks/time-window`) et qu’une sauvegarde reflète les nouveaux paramètres.
4. **Polling IMAP** : dans l’onglet Polling, contrôler l’état `enable_polling`, les jours/heures actifs et les expéditeurs surveillés.
5. **Administration** : en cas d’échec Render, utiliser l’onglet Administration pour déclencher `/api/deploy_application` (ordre Hook → API → fallback).
6. **Toasts & logs UI** : surveiller les alertes rouges/orange; la moindre erreur d’API post-déploiement doit être corrélée avec les logs Render.

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

## Sécurité Frontend Renforcée (2026-01-18)

### Protection XSS

- **Construction DOM sécurisée** : Remplacement de `innerHTML` par création sécurisée d'éléments DOM dans `loadWebhookLogs()`
- **Validation des entrées** : Contrôle systématique des champs avant envoi API
- **Échappement automatique** : Protection contre les injections dans les affichages utilisateur

### Conditional Logging

- **Protection des données sensibles** : `console.log/error/warn` uniquement exécutés en localhost/127.0.0.1
- **Production sécurisée** : Aucune exposition de données sensibles en production
- **Débogage préservé** : Logs complets disponibles en environnement de développement

### Gestion Centralisée des Erreurs

- **ApiClient centralisé** : Gestion automatique des erreurs 401/403 avec redirection vers `/login`
- **Sessions expirées** : Redirection transparente lorsque la session n'est plus valide
- **Accès refusé** : Messages clairs pour les erreurs 403 et erreurs serveur

### Validation Robuste

- **Validation placeholders** : Blocage de l'envoi si champ égal au placeholder "Non configuré"
- **Validation formats horaires** : Acceptation `HHhMM` et `HH:MM` avec normalisation automatique
- **Contrôles client-side** : Validation immédiate avec feedback utilisateur

## Performance & Accessibilité (2026-01-18)

### Architecture Modulaire ES6

- **Réduction taille bundle** : Refactorisation de 1488 → ~600 lignes pour `dashboard.js`
- **Lazy loading** : Chargement différé des onglets via `TabManager`
- **Modules spécialisés** : Séparation claire des responsabilités (API, webhooks, logs, UI)

### Responsive Design Mobile-First

- **Breakpoints optimisés** : 768px (tablettes) et 480px (mobile)
- **Grid adaptatif** : `minmax(300px, 1fr)` pour les conteneurs
- **Navigation mobile** : Interface optimisée pour écrans tactiles

### Accessibilité WCAG AA

- **Rôles ARIA complets** : `tablist`, `tab`, `tabpanel` avec états appropriés
- **Navigation clavier** : Support complet Tab/Shift+Tab/Espace/Entrée
- **Screen readers** : Labels et descriptions appropriés
- **Contrastes visuels** : Respect des ratios de contraste WCAG AA

### Optimisations Performance

- **Timer intelligent** : Polling avec `visibility API` pour pause/resume automatique
- **Animations CSS** : Transitions fluides sans impact performance
- **Gestion mémoire** : Nettoyage automatique des timers et écouteurs d'événements
- **Cache intelligent** : Mise en cache des réponses API avec invalidation appropriée

### États de Chargement

- **Spinners cohérents** : Indicateurs de chargement unifiés via `MessageHelper`
- **Skeleton screens** : Placeholder visuel pendant le chargement des données
- **Feedback utilisateur** : Messages clairs pendant les opérations asynchrones

## Architecture Technique Frontend

### Services Frontend Spécialisés

#### ApiService
- Client API centralisé avec gestion 401/403
- Méthodes `get()`, `post()`, `request()` avec error handling
- Redirection automatique vers login en cas de session expirée

#### WebhookService  
- Gestion complète configuration webhooks
- Affichage sécurisé des logs (construction DOM)
- Validation des entrées utilisateur

#### LogService
- Timer polling intelligent avec visibility API
- Export JSON des logs
- Gestion automatique du cycle de vie du polling

#### TabManager
- Gestion des onglets avec accessibilité ARIA
- Lazy loading des sections
- Navigation clavier complète

#### MessageHelper
- Utilitaires UI unifiés (messages, loading)
- Validation des formats (temps, email)
- Feedback utilisateur cohérent

### Intégration Backend

- **Appels API REST** : Communication avec services backend via endpoints standardisés
- **Gestion des erreurs** : Centralisation et affichage utilisateur approprié
- **Mise à jour optimiste** : Interface mise à jour immédiatement avec synchronisation backend
- **Cache serveur** : Invalidation du cache lors des modifications critiques
