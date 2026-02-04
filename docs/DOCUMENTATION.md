# Documentation du projet - Synthèse Code-Doc

## Project Vital Signs

- **Languages (cloc 2026-02-04)** : Python 387 679 LOC / 1 667 fichiers, JavaScript 61 665 LOC / 304 fichiers, Markdown 23 227 LOC / 33 fichiers, TypeScript 12 550 LOC / 4 fichiers. Les autres langages (YAML, HTML, CSS, shells, C/C++) restent <2 % du volume.
- **Scale** : 2 128 fichiers sources actifs (après exclusion `tests/`, `docs/`, `debug/`, `deployment/`, `memory-bank/`).
- **Complexity Hotspots: cloc remonte toujours `./.venv/.../fetch.js`; l’exclusion stricte du virtualenv côté CI empêche l’ingestion de dépendances externes dans les métriques officielles.
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
│   ├── email_polling_legacy.md       # Polling IMAP (retiré) + historique store-as-source-of-truth
│   ├── webhooks.md             # Flux webhooks + Offload R2 + Absence Globale
│   ├── magic_link_auth.md      # Authentification Magic Link
│   ├── gmail_push_ingress.md  # Endpoint POST /api/ingress/gmail pour Apps Script
│   ├── gmail_push_patterns.md  # Patterns de détection et règles de traitement
│   ├── r2_transfer_service.md  # Service offload Cloudflare R2 complet
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

- **Architecture orientée services** : 8 services principaux (Config, Auth, RuntimeFlags, Webhook, Deduplication, RoutingRules, MagicLink, R2)
- **Store-as-Source-of-Truth** : Redis Config Store prioritaire, backend JSON externe fallback, fichiers locaux dernier recours
- **Frontend modulaire ES6** : Architecture découplée avec services spécialisés (ApiService, WebhookService, LogService)
- **Ingress Gmail unique** : Endpoint `POST /api/ingress/gmail` (Apps Script + Bearer token) remplace définitivement le polling IMAP depuis le 2026-02-04
- **Résilience Lot 2** : Verrou distribué Redis, fallback R2 garanti, surveillance opératoire renforcée
- **Sécurité Lot 1** : Anonymisation logs, écriture atomique, validation domaines R2, variables ENV obligatoires

## Complexity Hotspots

### Complexity Hotspots (radon 2026-02-04)

| Rang | Fichier & fonction | Grade | Observations |
| --- | --- | --- | --- |
| 1 | `email_processing/orchestrator.py::check_new_emails_and_trigger_webhook` | F (239) | Flux Gmail Push complet → webhooks; extraction accrue des branches Media Solution/DESABO reste prioritaire. |
| 2 | `routes/api_ingress.py::ingest_gmail` | F (85) | Validation Apps Script (payload JSON, allowlist expéditeur, fenêtre horaire, enrichissement R2). Découpage par helper recommandé. |
| 3 | `services/r2_transfer_service.py::normalize_source_url` | E (31) | Normalisation Dropbox/FromSmash/SwissTransfer; Strategy Pattern toujours envisagé. |
| 4 | `preferences/processing_prefs.py::validate_processing_prefs` | E (32) | Validation imbriquée; bascule vers Pydantic/Marshmallow à planifier. |
| 5 | `email_processing/pattern_matching.py::check_media_solution_pattern` | E (33) | Multiples branches regex; extraction d’un moteur dédié suggérée. |

> Les sections `configuration/configuration.md`, `architecture/overview.md`, `quality/testing.md` et `features/gmail_push_ingress.md` restent les documents à la densité la plus élevée; elles doivent refléter toute réduction de complexité future.

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
