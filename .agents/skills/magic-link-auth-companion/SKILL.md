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
- ENV obligatoires : `FLASK_SECRET_KEY`.
- ENV recommandées : `MAGIC_LINK_TTL_SECONDS` pour piloter la durée de vie; `MAGIC_LINK_TOKENS_FILE` reste optionnelle car `config/settings.py` fournit un fallback par défaut.
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
   - Pour les liens illimités (`unlimited=True` côté API/UI), exiger révocation explicite.
3. **Stockage**
   - Redis-first : via `app_config_store`.
   - Backend externe : endpoints `GET/POST magic_link_tokens` (PHP). Toujours vérifier les codes de retour et valider le JSON.
4. **Routes & UI**
   - API : réponses JSON `{success, magic_link, expires_at, unlimited}`.
   - UI : respecter les toasts (`MessageHelper`), `showCopiedFeedback`, états disabled pendant l'appel.
   - Ajouter les boutons/options (illimité, TTL custom éventuel) dans des panneaux accessibles, sans casser le flux actuel `generateMagicLink()` de `static/dashboard.js`.
5. **Tests**
   - `pytest tests/test_services.py -k magic_link` pour couvrir le service actuel.
   - Compléter `tests/test_api_auth.py` ou ajouter un fichier dédié si la surface API `/api/auth/magic-link` s'élargit.
   - QA manuelle : génération one-shot, permanent, révocation.
6. **Documentation & Memory Bank**
   - Mettre à jour `docs/access/authentication.md` (section Magic Links) ou section correspondante.
   - Consigner toute nouvelle option de sécurité dans la Memory Bank.
7. **Revocation (urgence)**
   - Utiliser le helper `python ./.agents/skills/magic-link-auth-companion/revoke_magic_links.py --all` ou `python ./.agents/skills/magic-link-auth-companion/revoke_magic_links.py --token <uuid>` pour révoquer en masse ou individuellement.

## Ressources
- `revoke_magic_links.py` : script CLI pour révoquer tous les tokens (`--all`) ou un token spécifique (`--token <uuid>`).

## Conseils
- Utiliser des UUID v4 pour les tokens et vérifier les collisions.
- Nettoyer les tokens expirés régulièrement (ex: au démarrage et après chaque génération).
- Lors d'une compromission, fournir un script de révocation de masse (via `set_config_json`).
