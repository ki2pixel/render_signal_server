# Journal des Décisions (Chronologie Inversée)
Ce document enregistre les décisions techniques et architecturales importantes prises au cours du projet.

## Archives disponibles
Les périodes antérieures sont archivées dans `/memory-bank/archive/` :
- [decisionLog_2025Q4.md](archive/decisionLog_2025Q4.md) - Archives Q4 2025 (décembre 2025 et antérieur)

## Highlights 2025 Q4
- **Standardisation des environnements virtuels** (2025-12-21) : Priorité à l'environnement partagé `/mnt/venv_ext4/venv_render_signal_server` avec alternative locale.
- **Architecture orientée services finalisée** (2025-11-17) : 6 services (ConfigService, RuntimeFlagsService, WebhookConfigService, AuthService, PollingConfigService, DeduplicationService) intégrés, 83/83 tests OK.
- **Absence Globale** (2025-11-21/24) : Refactoring terminologique "presence_pause" → "absence_pause" et application stricte avec garde de cycle.
- **Refactoring email_processing** (2025-11-18) : TypedDict, helpers extraits, types sécurisés, 282 tests OK.
- **Suppression fonctionnalité "Presence"** (2025-11-18) : Nettoyage complet du code obsolète.

---

## Politique d'archivage
Les périodes antérieures à 90 jours sont archivées dans `/memory-bank/archive/` par trimestre. Les entrées actuelles conservent uniquement les décisions récentes. Voir les archives pour l'historique détaillé.

---

## Entrées récentes (post-archives)

- **[2026-01-06 11:27:00] - Réduction de la dette historique des Memory Bank**
  - **Décision** : Mettre en œuvre une politique d'archivage pour réduire la taille de `decisionLog.md` (>1000 lignes) et `progress.md` (~350 lignes) tout en conservant l'historique utile.
  - **Changements clés** :
    - Création du dossier `/memory-bank/archive/` avec fichiers trimestriels (`decisionLog_2025Q4.md`, `progress_2025Q4.md`)
    - Consolidation des entrées redondantes en résumés thématiques (Absence Globale, refactoring services)
    - Ajout de sections "Archives disponibles" et "Highlights 2025 Q4" dans les fichiers principaux
    - Déplacement des entrées antérieures à 2025-12-01 vers les archives
  - **Raisons** : Les fichiers devenaient difficiles à maintenir et contenaient beaucoup de redondances. L'archivage améliore la lisibilité tout en préservant l'historique.
  - **Impacts** : Fichiers principaux réduits à <100 lignes, historique préservé dans archives, politique de maintenance claire établie.
