# Contexte Actif

## Tâches Terminées
- [2026-01-14] **Lot 2 - Résilience & Architecture** :
  - Verrou distribué Redis (fallback fcntl + warning) dans `background/lock.py`.
  - Fallback R2 garanti dans `email_processing/orchestrator.py` (conservation URLs sources, try/except, log WARNING, flux continu).
  - Watchdog IMAP timeout (30s) dans `email_processing/imap_client.py`.
  - Tests unitaires Redis lock créés (`tests/test_lock_redis.py`) et adaptation tests existants.
  - Validation : 386 passed, 13 skipped, 0 failed (exécuté dans `/mnt/venv_ext4/venv_render_signal_server`), couverture 70.12%.
- [2026-01-13] **Lot 1 - Sécurité & PII** :
  - Anonymisation des logs (sujets, emails, contenu) via `mask_sensitive_data`.
  - Sécurisation des services de config (RLock + écriture atomique).
  - Validation préventive des domaines pour l'offload R2 (anti-SSRF).

## Prochaine Étape
- Aucune tâche active. Lot 2 terminé avec succès.
