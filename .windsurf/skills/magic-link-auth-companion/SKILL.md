---
name: magic-link-auth-companion
description: Manage MagicLinkService changes across backend, storage (Redis/external), and dashboard UI while enforcing security, TTL, and revocation requirements.
---

# Magic Link Auth Companion

## Quand utiliser ce skill
- Modifications de `services/magic_link_service.py`
- API `/api/auth/magic-link`
- UI `login.html`, `dashboard.html`, `static/dashboard.js`
- Stockage Redis ou backend externe (`config_api.php`)

## Pré-requis
- ENV obligatoires (mode Redis-first) : `FLASK_SECRET_KEY`, `MAGIC_LINK_TOKENS_FILE`.
- ENV optionnelles (mode backend externe) : `EXTERNAL_CONFIG_BASE_URL`, `CONFIG_API_TOKEN`.
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` pour les scripts.
- Accès Redis ou backend externe fonctionnel.

## Workflow
1. **Sécurité & ENV**
   - Vérifier les ENV ci-dessus.
   - Interdire toute journalisation des tokens (utiliser `mask_sensitive_data`).
2. **Service Python**
   - Garder le pattern singleton + `RLock`.
   - Assurer la signature HMAC SHA-256, TTL configurable (`MAGIC_LINK_TTL_SECONDS`).
   - Pour les tokens permanents (`single_use=False`), exiger révocation explicite.
3. **Stockage**
   - Redis-first : via `app_config_store`.
   - Backend externe : endpoints `GET/POST magic_link_tokens` (PHP). Toujours vérifier les codes de retour et valider le JSON.
4. **Routes & UI**
   - API : réponses JSON `{link, expires_at, single_use}`.
   - UI : respecter les toasts (`MessageHelper`), `showCopiedFeedback`, états disabled pendant l'appel.
   - Ajouter les boutons/options (illimité, TTL custom) dans des panneaux accessibles.
5. **Tests**
   - `pytest tests/test_magic_link_service.py` (ou fichier équivalent).
   - Ajouter tests API (`tests/routes/test_api_auth_magic_link.py` si présent) pour les nouveaux paramètres.
   - QA manuelle : génération one-shot, permanent, révocation.
6. **Documentation & Memory Bank**
   - Mettre à jour `docs/auth/magic_link.md` ou section correspondante.
   - Consigner toute nouvelle option de sécurité dans la Memory Bank.
7. **Revocation (urgence)**
   - Utiliser le helper `./.windsurf/skills/magic-link-auth-companion/revoke_magic_links.py` pour révoquer en masse ou individuellement.

## Ressources
- `revoke_magic_links.py` : script CLI pour révoquer tous les tokens (`--all`) ou un token spécifique (`--token <uuid>`).

## Conseils
- Utiliser des UUID v4 pour les tokens et vérifier les collisions.
- Nettoyer les tokens expirés régulièrement (ex: au démarrage et après chaque génération).
- Lors d'une compromission, fournir un script de révocation de masse (via `set_config_json`).
