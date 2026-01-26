# Documentation du projet

Ce dossier contient la documentation fonctionnelle et technique de l'application **Render Signal Server**.

La documentation est organisée pour répondre aux besoins des développeurs, opérateurs et administrateurs système, avec une attention particulière portée à la maintenabilité et à la qualité du code.

## 📚 Plan de documentation

### Architecture et Conception
- `architecture/overview.md` - Vue d'ensemble de l'architecture orientée services (Magic Links, R2, Lot 2)
- `architecture/api.md` - Documentation complète de l'API REST (endpoints Magic Link, store-as-source-of-truth)
- `features/frontend_dashboard_features.md` - Architecture modulaire ES6 et fonctionnalités UX avancées

### Traitement des e-mails & Webhooks
- `features/email_polling.md` - Polling IMAP et orchestrateur de traitement (store-as-source-of-truth)
- `features/webhooks.md` - Flux webhooks sortants, Absence Globale et fenêtres horaires
- `features/magic_link_auth.md` - Authentification Magic Link sans mot de passe

### Résilience & Sécurité
- `securite.md` - Durcissement sécurité (Lot 1) : Anonymisation logs, écriture atomique, validation R2, variables ENV obligatoires
- `features/resilience_lot2.md` - Résilience & Architecture (Lot 2) : Verrou Redis, Fallback R2, Watchdog IMAP

### Déploiement et Opérations
- `operations/deploiement.md` - Déploiement Flask (Gunicorn/Nginx) et couche PHP associée
- `operations/operational-guide.md` - Comportement Render Free, Gunicorn et health checks
- `operations/multi-container-deployment.md` - Guide déploiement multi-conteneurs avec Redis (Lot 2)
- `operations/checklist_production.md` - Check-list de mise en production
- `operations/depannage.md` - Guide de dépannage (problèmes courants)
- `operations/skills.md` - Référence des skills Windsurf avec helpers et workflows

### Configuration & Stockage
- `configuration/configuration.md` - Référence des paramètres de configuration et variables d'environnement (obligatoires)
- `configuration/storage.md` - Backend JSON externe, Redis Config Store, fallback fichiers, artefacts Gmail OAuth
- `configuration/installation.md` - Guide d'installation et configuration initiale

### Tests & Qualité
- `quality/testing.md` - Stratégie de tests, exécution et couverture de code (Lot 2, markers Redis/R2)
- `quality/performance.md` - Métriques performance et surveillance

### Intégrations
- `integrations/r2_offload.md` - Offload Cloudflare R2 pour économiser la bande passante
- `integrations/r2_dropbox_limitations.md` - Limitations et solutions pour les dossiers Dropbox partagés
- `integrations/gmail-oauth-setup.md` - Configuration détaillée de l'authentification Gmail OAuth

### Refactoring & Historique
- `archive/refactoring/` - Historique détaillé des phases de refactoring (incluant roadmap & conformity report)
- `archive/achievements/ACHIEVEMENT_100_PERCENT.md` - Badge "100% refactoring" (historique)

---

## 📊 Métriques de Documentation

- **Volume** : 25 fichiers Markdown actifs, 7 388 lignes de contenu (densité >7k lignes justifiant le découpage modulaire)
- **Structure** : 6 sous-domaines thématiques (architecture, configuration, features, operations, integrations, quality)
- **Exclusions** : `archive/` et `audits/` exclus pour maintenir la documentation active à jour
- **Mise à jour** : 2026-01-25 (refonte complète selon protocol code-doc)

---

## 📅 Dernière mise à jour / Engagements Lot 2

**Date de refonte** : 2026-01-25 (protocol code-doc)

### Terminologie unifiée
- **`DASHBOARD_*`** : Variables d'environnement (anciennement `TRIGGER_PAGE_*`)
- **`MagicLinkService`** : Service singleton pour authentification sans mot de passe
- **`R2TransferService`** : Service singleton pour offload Cloudflare R2
- **"Absence Globale"** : Fonctionnalité de blocage configurable par jour de semaine

### Engagements Lot 2 (Résilience & Architecture)
- ✅ **Verrou distribué Redis** : Implémenté avec clé `render_signal:poller_lock`, TTL 5 min
- ✅ **Fallback R2 garanti** : Conservation URLs sources si Worker R2 indisponible
- ✅ **Watchdog IMAP** : Timeout 30s pour éviter processus zombies
- ✅ **Tests résilience** : `test_lock_redis.py`, `test_r2_resilience.py` avec marqueurs `@pytest.mark.redis`/`@pytest.mark.r2`
- ✅ **Store-as-Source-of-Truth** : Configuration dynamique depuis Redis/fichier, pas d'écriture runtime dans les globals

### Métriques de documentation
- **Volume** : 7 388 lignes de contenu réparties dans 25 fichiers actifs
- **Densité** : Justifie le découpage modulaire pour maintenir la lisibilité
- **Exclusions** : `archive/` et `audits/` maintenus séparément pour éviter le bruit

## 🚀 Aperçu rapide

### 🔄 Architecture Orientée Services (2025-11)

#### Services Principaux
- **`ConfigService`** - Gestion centralisée de la configuration
- **`AuthService`** - Authentification et autorisation
- **`RuntimeFlagsService`** - Gestion dynamique des fonctionnalités (Singleton)
- **`WebhookConfigService`** - Configuration et validation des webhooks (Singleton)
- **`DeduplicationService`** - Prévention des doublons (Redis + fallback mémoire)
- **`PollingConfigService`** - Configuration du polling IMAP
- **`MagicLinkService`** - Gestion des magic links pour authentification sans mot de passe (Singleton)
- **`R2TransferService`** - Offload Cloudflare R2 pour économiser la bande passante (Singleton)

#### Avantages Clés
- **Maintenabilité** : Séparation claire des responsabilités
- **Testabilité** : Injection de dépendances facilitée
- **Performance** : Cache TTL 60s pour les opérations coûteuses
- **Évolutivité** : Architecture modulaire et extensible

### 📧 Orchestrateur de Traitement des Emails

#### Fonctionnalités
- Récupération robuste des emails (reconnexion automatique)
- Détection intelligente des types d'emails
- Gestion des fenêtres temporelles
- **Absence Globale** : Blocage configurable des envois par jour de semaine
- Déduplication avancée (ID + groupe de sujets)
- Journalisation détaillée

#### Intégrations
- **IMAP** : Support de multiples fournisseurs
- **Webhooks** : Envoi asynchrone avec gestion des erreurs
- **Redis** : Cache et déduplication (optionnel)
- **Cloudflare R2** : Offload automatique des fichiers volumineux via `R2TransferService`

### 🧪 Qualité et Tests
- **Tests unitaires** : 418/431 tests passants (97%) - Post-Lot 2
- **Couverture de code** : 70.12% (objectif : 80%+) - Post-Lot 2
- **Intégration continue** : Pipelines automatisés (GitHub Actions)
- **Nouveaux tests** : Redis lock, R2 resilience, Given/When/Then avec marqueurs `@pytest.mark.redis`/`@pytest.mark.r2`/`@pytest.mark.resilience`

### 🔒 Sécurité
- **Authentification sécurisée** : Sessions Flask-Login et Magic Links signés HMAC SHA-256
- **Validation des entrées** : Contrôles stricts et sanitization
- **Journalisation des actions sensibles** : Logs structurés et traçabilité, anonymisation PII via `mask_sensitive_data()`
- **Gestion sécurisée des secrets** : Variables d'environnement obligatoires (8 variables), enforcement au démarrage
- **Écriture atomique configuration** : Services avec `RLock` + `os.replace()` pour prévenir la corruption
- **Validation domaines R2** : Allowlist stricte anti-SSRF, fallback gracieux

### 🚀 Nouvelles fonctionnalités (2026)

#### 🎯 Absence Globale
- Blocage complet des webhooks sur des jours spécifiques
- Configuration via dashboard ou API `/api/webhooks/config`
- Priorité maximale, ignore les autres règles

#### 🔐 Authentification Magic Link
- Service `MagicLinkService` pour tokens signés HMAC
- Endpoint `/api/auth/magic-link` (session requise)
- Support one-shot et permanent, stockage partagé via API PHP

#### ☁️ Offload Cloudflare R2
- Service `R2TransferService` pour économiser bande passante
- Worker Cloudflare avec authentification `X-R2-FETCH-TOKEN`
- Persistance paires `source_url`/`r2_url` dans `webhook_links.json`

#### 🐳 Déploiement Docker GHCR
- Workflow GitHub Actions pour build/push GHCR
- Déclenchement Render via Deploy Hook ou API
- Image Docker avec Gunicorn et logs centralisés

#### 🛡️ Résilience & Architecture (Lot 2)
- **Verrou distribué Redis** : Clé `render_signal:poller_lock`, TTL 5 min, fallback fcntl
- **Fallback R2 garanti** : Conservation URLs sources, flux continu même si R2 échoue
- **Watchdog IMAP** : Timeout 30s paramétrable, prévention connexions zombies
- **Tests Résilience** : Format Given/When/Then avec marqueurs `@pytest.mark.redis`/`@pytest.mark.r2`/`@pytest.mark.resilience`
- **Store-as-Source-of-Truth** : Configuration dynamique depuis Redis/fichier, pas d'écriture runtime dans les globals

## 📅 Historique des Évolutions

### 🔄 Améliorations Récentes (2025-11)

#### Architecture et Performance
- **Refonte complète** en architecture orientée services
- **Optimisation** des performances avec système de cache TTL
- **Amélioration** de la gestion des erreurs et des reprises

#### Interface Utilisateur
- **Tableau de bord** repensé pour une meilleure expérience
- **Visualisation en temps réel** des logs et des métriques
- **Gestion simplifiée** des configurations

#### Sécurité
- **Renforcement** de l'authentification
- **Amélioration** de la validation des entrées
- **Journalisation** détaillée des actions sensibles

### 🛠 Améliorations Techniques (2025-10)

#### Refactorisation Modulaire
- Extraction des composants dans des modules dédiés :
  - `auth/` : Gestion de l'authentification
  - `config/` : Configuration de l'application
  - `utils/` : Fonctions utilitaires
  - `email_processing/` : Traitement des emails

#### Détection des Emails
- **Pattern Matching** avancé dans `email_processing/pattern_matching.py`
- Détection des fournisseurs via `URL_PROVIDERS_PATTERN`
- Gestion des différents types d'emails (Média Solution, DESABO, etc.)

#### Interface Utilisateur
- Navigation intuitive par onglets
- Gestion des flags runtime
- Consultation des logs en temps réel

#### Webhooks
- Format de payload standardisé
- Gestion des fenêtres temporelles
- Support de multiples fournisseurs (Make.com, webhooks personnalisés)

## 🧪 Environnement de Développement

### Simulation des Webhooks

Un script de simulation permet de tester les fonctionnalités sans dépendre d'une boîte mail ou d'appels HTTP réels.

#### Scripts Disponibles
- `debug/simulate_webhooks.py` - Simule l'envoi de webhooks avec différents scénarios
- `debug/test_imap_connection.py` - Teste la connexion IMAP avec les paramètres actuels
- `debug/generate_test_emails.py` - Génère des emails de test dans une boîte mail

#### Utilisation de Base

```bash
# Désactiver les tâches en arrière-plan et simuler les webhooks
DISABLE_BACKGROUND_TASKS=true \
FLASK_APP=app_render.py \
python debug/simulate_webhooks.py
```

#### Scénarios Supportés

- **Fournisseurs de Stockage**
  - Dropbox (avec rétrocompatibilité)
  - FromSmash
  - SwissTransfer
  
- **Types d'Emails**
  - Média Solution
  - Désabonnement (DESABO)
  - Autres types personnalisés

- **Cas d'Erreur**
  - Timeout de connexion
  - Réponses d'erreur
  - Données manquantes ou invalides

#### Sortie du Script

Le script affiche :
- Les payloads JSON générés
- Les appels HTTP simulés (sans trafic réseau réel)
- Les erreurs éventuelles
- Les statistiques d'exécution

### Tests et Vérifications

#### Exécution des Tests

```bash
# Exécuter tous les tests
pytest

# Exécuter les tests avec couverture de code
pytest --cov=.

# Générer un rapport de couverture HTML
pytest --cov=. --cov-report=html
```

#### Vérification du Code

```bash
# Vérifier le style de code avec flake8
flake8 .

# Vérifier les types avec mypy
mypy .

# Vérifier les vulnérabilités de sécurité
safety check
```

## 🤝 Contribution

Les contributions sont les bienvenues ! Veuillez consulter le guide de contribution pour plus d'informations.

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙋‍♂️ Support

Pour toute question ou problème, veuillez ouvrir une issue sur le dépôt GitHub.
