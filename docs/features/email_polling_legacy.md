# 🚫 IMAP Polling - Historique (Retiré)

**Date de retrait** : 2026-02-04  
**Statut** : ❌ **RETIRED** - Le polling IMAP a été complètement supprimé et remplacé par Gmail Push Ingestion.

---

## ⚠️ Important - Ce document est historique

Le polling IMAP a été **complètement retiré** du projet le 2026-02-04.  
Pour l'ingestion actuelle des e-mails, consultez :

- ✅ **[Gmail Push Ingress](gmail_push_ingress.md)** - Endpoint `POST /api/ingress/gmail`
- ✅ **[Architecture Overview](../architecture/overview.md)** - Vue d'ensemble avec Gmail Push
- ✅ **[Configuration](../configuration/configuration.md)** - Variables d'environnement actuelles

---

## Historique du Polling IMAP (2025-11-18 → 2026-02-04)

### Dernière configuration connue

Le polling des emails était géré par le thread `background_email_poller()` qui exécutait en boucle les opérations de vérification et de traitement des emails.

### Source de vérité Redis (historique)

- **Service** : `PollingConfigService` lisait les valeurs persistées via `config/app_config_store.get_config_json("polling_config")`.
- **Structure JSON** (clé `polling_config` dans Redis) :

  | Champ | Type | Description |
  | --- | --- | --- |
  | `active_days` | `list[int]` | Jours actifs (0 = lundi). Validés/triés, fallback settings si vide |
  | `active_start_hour` / `active_end_hour` | `int` | Fenêtre horaire 0-23 (validation stricte, erreur 400 côté API si hors plage) |
  | `sender_of_interest_for_polling` | `list[str]` | Adresses email normalisées/uniques (regex stricte) |
  | `enable_subject_group_dedup` | `bool` | Active la déduplication mensuelle côté orchestrateur |
  | `vacation_start` / `vacation_end` | `YYYY-MM-DD or null` | Fenêtre vacances optionnelle, validée et convertie en ISO |
  | `enable_polling` | `bool` | Toggle UI combiné avec `ENABLE_BACKGROUND_TASKS` pour lancer/arrêter le thread |

### Conditions de démarrage (historique)

- `ENABLE_BACKGROUND_TASKS=true` (variable d'environnement)
- `enable_polling=true` (persisté dans la clé Redis `polling_config`)

Les deux conditions devaient être vraies pour démarrer le thread.

### Composants retirés

Les modules suivants ont été **supprimés** lors de la retraite du polling IMAP :

- `background/polling_thread.py` - Boucle de polling IMAP (135 lignes)
- `background/lock.py` - Verrouillage inter-processus (76 lignes)
- `config/polling_config.py` - Service de configuration polling (197 lignes)
- `routes/api_polling.py` - Endpoint toggle polling (44 lignes)
- `email_processing/imap_client.py` - Client IMAP avec timeout
- Tests associés : `test_background_lock*.py`, `test_lock_redis.py`, `test_background_polling_thread.py`, `test_config_polling_config.py`
- Skill `.windsurf/skills/background-poller-resilience-lab/` - Tests de résilience

### Variables d'environnement retirées

Les variables suivantes sont maintenant **legacy optionnelles** (uniquement pour les tests) :

- `ENABLE_BACKGROUND_TASKS` - Plus requis en production
- `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER` - Identifiants IMAP
- `EMAIL_POLLING_INTERVAL_SECONDS` - Intervalle de polling
- `POLLING_INACTIVE_CHECK_INTERVAL_SECONDS` - Intervalle inactif
- `BG_POLLER_LOCK_FILE` - Chemin du fichier de lock

---

## Migration vers Gmail Push

### Pourquoi le changement ?

1. **Fiabilité** : Gmail Apps Script élimine les limitations IMAP (quotas, timeouts)
2. **Simplicité** : Plus besoin de tâches de fond, de verrous distribués
3. **Performance** : Ingestion instantanée vs polling périodique
4. **Maintenance** : Réduction de la complexité du code

### Configuration actuelle

- **Endpoint** : `POST /api/ingress/gmail`
- **Authentification** : Bearer token `PROCESS_API_TOKEN`
- **Documentation** : [gmail_push_ingress.md](gmail_push_ingress.md)

---

## Références

- **Plan de retraite complet** : [retirement_imap_polling_plan.md](../retirement_imap_polling_plan.md)
- **Documentation Gmail Push** : [gmail_push_ingress.md](gmail_push_ingress.md)
- **Architecture actuelle** : [overview.md](../architecture/overview.md)

---

*Ce document est conservé à titre historique. Toute référence au polling IMAP doit être remplacée par Gmail Push Ingress.*
