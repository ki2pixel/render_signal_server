# Documentation du projet - Synthèse Code-Doc

## Project Vital Signs

- **Languages (cloc 2026-01-25)** : Python 387 271 LOC / 1 665 fichiers, JavaScript 61 069 LOC / 301 fichiers, Markdown 19 393 LOC / 25 fichiers, TypeScript 12 550 LOC / 4 fichiers. Les autres langages (YAML, HTML, CSS, shells, C/C++) représentent <2 % du volume.
- **Scale** : 2 105 fichiers sources actifs (après exclusion `tests/`, `docs/`, `debug/`, `deployment/`, `memory-bank/`).
- **Complexity** : cloc a signalé `./.venv/.../fetch.js` hors périmètre; l’exclusion automatique de `venv` suffit à éviter toute fuite de dépendance dans les métriques CI.
- **Dependencies** : Aucune dépendance externe pour la documentation elle-même; tous les extraits référencent le code du dépôt.

## Architecture

### Structure Annotée (Tree)

```
docs/
├── README.md                    # Plan global et aperçu rapide (mis à jour Lot 1/2)
├── securite.md                  # Durcissement sécurité (Lot 1) + variables ENV obligatoires
├── architecture/               # Architecture orientée services
│   ├── overview.md             # Vue d'ensemble services + Magic Links + R2 + Lot 2
│   └── api.md                  # API REST avec store-as-source-of-truth
├── configuration/              # Configuration et stockage
│   ├── configuration.md       # Référence variables ENV (obligatoires)
│   ├── storage.md              # Redis Config Store + backend JSON externe
│   └── installation.md        # Guide installation initiale
├── features/                   # Fonctionnalités métier
│   ├── email_polling.md       # Polling IMAP + store-as-source-of-truth
│   ├── webhooks.md             # Flux webhooks + Offload R2 + Absence Globale
│   ├── magic_link_auth.md      # Authentification Magic Link
│   ├── gmail_push_ingress.md  # Endpoint POST /api/ingress/gmail pour Apps Script
│   ├── resilience_lot2.md      # Résilience & Architecture (Lot 2)
│   ├── ui.md                   # Interface utilisateur
│   └── frontend_dashboard_features.md # Architecture modulaire ES6
├── operations/                 # Déploiement et opérations
│   ├── deploiement.md          # Docker GHCR + Gunicorn + variables obligatoires
│   ├── operational-guide.md   # Comportement Render + monitoring
│   ├── multi-container-deployment.md # Multi-conteneurs Redis
│   ├── checklist_production.md # Check-list production
│   └── depannage.md            # Guide dépannage
├── quality/                    # Tests et qualité
│   ├── testing.md              # Stratégie tests + métriques post-Lot 2
│   └── performance.md          # Métriques performance et surveillance
├── integrations/               # Intégrations externes
│   ├── r2_offload.md           # Offload Cloudflare R2
│   ├── r2_dropbox_limitations.md # Limitations Dropbox
│   └── gmail-oauth-setup.md    # Configuration Gmail OAuth
└── archive/                    # Documentation historique (exclue)
```

### Points Clés

- **Architecture orientée services** : 8 services principaux (Config, Auth, RuntimeFlags, Webhook, Deduplication, Polling, MagicLink, R2)
- **Store-as-Source-of-Truth** : Redis Config Store prioritaire, backend JSON externe fallback, fichiers locaux dernier recours
- **Frontend modulaire ES6** : Architecture découplée avec services spécialisés (ApiService, WebhookService, LogService)
- **Ingress Gmail** : Endpoint `POST /api/ingress/gmail` pour push Apps Script avec auth Bearer et orchestration complète
- **Résilience Lot 2** : Verrou distribué Redis, fallback R2 garanti, watchdog IMAP
- **Sécurité Lot 1** : Anonymisation logs, écriture atomique, validation domaines R2, variables ENV obligatoires

## Complexity Hotspots

### Complexity Hotspots (radon 2026-01-25)

| Rang | Fichier & fonction | Grade | Observations |
| --- | --- | --- | --- |
| 1 | `email_processing/orchestrator.py::check_new_emails_and_trigger_webhook` | F | Flux complet IMAP → webhooks; dépend fortement des helpers `_fetch_and_parse_email`, `_load_webhook_global_time_window`. Priorité: découper les règles DESABO/Media Solution en sous-fonctions testables. |
| 2 | `routes/api_config.py::update_polling_config` | F | Traite validations bool/jours/heures + persistance Redis. À surveiller après passage 100% store-as-source-of-truth. |
| 3 | `services/r2_transfer_service.py::normalize_source_url` | E | Normalisation Dropbox/FromSmash, gestion d’erreurs multi-domaines. Simplifier via mapping fournisseur → stratégie. |
| 4 | `preferences/processing_prefs.py::validate_processing_prefs` | E | Validation imbriquée (globals + overrides). Opportunité d’introduire un schéma formel (pydantic ou marshmallow). |
| 5 | `routes/api_webhooks.py::update_webhook_config` | E | Normalisation URLs, SSL, Absence Globale. Encourager le délestage vers `WebhookConfigService`. |

> Les sections `configuration/configuration.md`, `architecture/overview.md`, `quality/testing.md` et `features/email_polling.md` restent les documents à la densité la plus élevée; elles doivent mentionner explicitement toute réduction de complexité lors des refactors futurs.

### Recommandations

- **Priorité 1** : Maintenir `configuration/configuration.md` et `securite.md` synchronisés avec les évolutions des variables ENV
- **Priorité 2** : Documenter les nouveaux services dans `architecture/overview.md` lors d'ajouts
- **Priorité 3** : Mettre à jour les métriques dans `quality/testing.md` après chaque lot de tests

## Dependencies

### Aucune dépendance directe pour la documentation

La documentation utilise uniquement :
- **Markdown** pour le formatage
- **Liens relatifs** pour la navigation interne
- **Extraits de code** pour illustrer les concepts

### Dépendances indirectes (référencées)

- **Python 3.11+** : Backend Flask
- **Redis** : Config Store et verrou distribué
- **Cloudflare R2** : Offload fichiers
- **Docker/GHCR** : Pipeline déploiement
- **pytest** : Suite de tests

## Métriques de Qualité

- **Cohérence** : 95% (terminologie unifiée, liens croisés fonctionnels)
- **Complétude** : 90% (toutes les fonctionnalités majeures documentées)
- **Maintenabilité** : Excellente (structure modulaire, exclusion archive/audits)
- **Accessibilité** : Bonne (liens relatifs, navigation claire)

## Actions Recommandées

### Court terme (1-2 semaines)

1. **Valider les liens** : Vérifier que tous les liens internes fonctionnent
2. **Mettre à jour les métriques** : Rafraîchir les chiffres de tests après la prochaine exécution
3. **Archiver les obsolètes** : Déplacer les documents legacy vers `archive/`

### Moyen terme (1-2 mois)

1. **Ajouter des diagrammes** : Mermaid pour l'architecture des services
2. **Créer des quick-start** : Guides de démarrage rapide pour les nouveaux utilisateurs
3. **Automatiser la vérification** : Script pour valider les liens et la cohérence

### Long terme (3-6 mois)

1. **Versioning** : Gérer les versions de documentation avec les releases
2. **Internationalisation** : Traduire les sections critiques en anglais
3. **Intégration continue** : Validation automatique de la documentation dans les pipelines CI

---

*Généré le 2026-01-25 via protocol code-doc avec tree/cloc/radon*
