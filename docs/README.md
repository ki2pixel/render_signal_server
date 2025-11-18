# Documentation du projet

Ce dossier contient la documentation fonctionnelle et technique de l'application **Render Signal Server**.

La documentation est organisée pour répondre aux besoins des développeurs, opérateurs et administrateurs système, avec une attention particulière portée à la maintenabilité et à la qualité du code.

## 📚 Plan de documentation

### Architecture et Conception
- `architecture.md` - Vue d'ensemble de l'architecture orientée services
- `api.md` - Documentation complète de l'API REST
- `database.md` - Schéma de la base de données et migrations
- `testing.md` - Stratégie de tests et couverture de code

### Développement
- `installation.md` - Guide d'installation et configuration initiale
- `development.md` - Configuration de l'environnement de développement
- `coding_standards.md` - Standards de codage et bonnes pratiques
- `debugging.md` - Techniques de débogage et outils

### Déploiement et Opérations
- `deployment.md` - Guide de déploiement (Gunicorn, Nginx, Docker)
- `configuration.md` - Référence des paramètres de configuration
- `monitoring.md` - Surveillance et métriques
- `maintenance.md` - Tâches de maintenance courantes

### Référence
- `api_reference/` - Documentation technique détaillée de l'API
- `changelog.md` - Historique des changements
- `glossary.md` - Glossaire des termes techniques

## 🚀 Aperçu rapide

### 🔄 Architecture Orientée Services (2025-11)

#### Services Principaux
- **`ConfigService`** - Gestion centralisée de la configuration
- **`AuthService`** - Authentification et autorisation
- **`RuntimeFlagsService`** - Gestion dynamique des fonctionnalités (Singleton)
- **`WebhookConfigService`** - Configuration et validation des webhooks (Singleton)
- **`DeduplicationService`** - Prévention des doublons (Redis + fallback mémoire)
- **`PollingConfigService`** - Configuration du polling IMAP

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
- Déduplication avancée (ID + groupe de sujets)
- Journalisation détaillée

#### Intégrations
- **IMAP** : Support de multiples fournisseurs
- **Webhooks** : Envoi asynchrone avec gestion des erreurs
- **Redis** : Cache et déduplication (optionnel)

### 🧪 Qualité et Tests
- **Tests unitaires** : 83/83 tests passants (100%)
- **Couverture de code** : ~67.3% (en amélioration continue)
- **Intégration continue** : Pipelines automatisés

### 🔒 Sécurité
- Authentification sécurisée
- Validation des entrées
- Journalisation des actions sensibles
- Gestion sécurisée des secrets

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
  - Présence
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
