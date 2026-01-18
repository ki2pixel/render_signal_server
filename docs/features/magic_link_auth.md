# Authentification Magic Link - Documentation

## Vue d'ensemble

Le système d'authentification par magic link permet un accès sécurisé et pratique au dashboard web sans nécessiter de mots de passe. Les tokens sont signés cryptographiquement et peuvent être configurés pour un usage unique ou permanent.

### Avantages

- **Accès sans mot de passe** : Génération de liens pré-authentifiés sécurisés
- **Tokens signés HMAC** : Protection cryptographique avec `FLASK_SECRET_KEY`
- **Flexibilité d'usage** : Tokens à usage unique (TTL) ou permanents (révocables)
- **Stockage partagé** : Support multi-workers Render via API PHP externe
- **Sécurité renforcée** : Logs détaillés, nettoyage automatique, permissions contrôlées

### Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Dashboard │────▶│ MagicLink    │────▶│ Token Store │
│   (UI)      │     │  Service     │     │ (JSON/API)  │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                     │
                           │                     ▼
                           │              ┌─────────────┐
                           │              │   Flask     │
                           │              │  Session    │
                           │              └─────────────┘
                           ▼
                    ┌──────────────┐
                    │   User       │
                    │  Access      │
                    └──────────────┘
```

**Flux détaillé** :

1. L'utilisateur authentifié génère un magic link via le dashboard
2. `MagicLinkService` crée un token signé HMAC SHA-256
3. Le token est stocké (fichier local ou API PHP externe)
4. L'utilisateur partage le lien (usage unique) ou le conserve (permanent)
5. L'accès au lien valide le token et crée la session Flask-Login
6. La session permet l'accès au dashboard jusqu'à expiration/révocation

---

## Configuration

### Variables d'environnement

#### Variables obligatoires

```bash
# Clé secrète pour signer les tokens (doit être robuste)
FLASK_SECRET_KEY=votre-clé-secrète-très-robuste

# Durée de validité des tokens à usage unique (secondes)
MAGIC_LINK_TTL_SECONDS=900  # 15 minutes par défaut
```

#### Variables optionnelles (stockage partagé)

```bash
# URL de l'API PHP pour le stockage partagé
EXTERNAL_CONFIG_BASE_URL=https://votre-domaine.tld

# Token d'authentification pour l'API PHP
CONFIG_API_TOKEN=token-hmac-partagé

# Répertoire de stockage côté PHP
CONFIG_API_STORAGE_DIR=/home/user/data/app_config
```

#### Fichiers de configuration

```bash
# Fichier local de stockage des tokens (fallback)
MAGIC_LINK_TOKENS_FILE=./magic_link_tokens.json
```

### Sécurité

- **Clé secrète** : `FLASK_SECRET_KEY` doit être robuste (64+ caractères aléatoires)
- **Permissions** : `chmod 600` sur le fichier de tokens
- **HTTPS** : Obligatoire en production pour les magic links
- **Token API** : `CONFIG_API_TOKEN` doit être identique côté Render et PHP

---

## Modes d'Utilisation

### Tokens à Usage Unique (One-Shot)

**Caractéristiques** :
- TTL configurable via `MAGIC_LINK_TTL_SECONDS` (défaut: 15 minutes)
- Auto-révocation après première utilisation
- Idéal pour les accès temporaires ou partages ponctuels

**Flux** :
1. Génération du token avec `single_use=True`
2. Partage du lien avec l'utilisateur
3. Première utilisation → création session + révocation automatique
4. Token invalide pour tout accès ultérieur

### Tokens Permanents

**Caractéristiques** :
- Pas d'expiration (TTL = `None`)
- Révocation manuelle requise si compromis
- Adapté pour les accès fréquents et administrateurs

**Flux** :
1. Génération avec `single_use=False` (option "illimité" dans l'UI)
2. Conservation du lien pour accès récurrent
3. Utilisation multiple sans expiration
4. Révocation manuelle si nécessaire (suppression du fichier)

---

## Stockage des Tokens

### Stockage Local (Fallback)

**Fichier** : `MAGIC_LINK_TOKENS_FILE` (défaut: `./magic_link_tokens.json`)

```json
{
  "abc123def456": {
    "created_at": "2026-01-19T12:00:00Z",
    "expires_at": "2026-01-19T12:15:00Z",
    "single_use": true,
    "used": false,
    "user_id": "admin"
  }
}
```

**Avantages** :
- Simple à configurer
- Pas de dépendance externe
- Rapide pour les déploiements mono-worker

**Inconvénients** :
- Non partagé entre workers Render
- Persistance limitée (filesystem éphémère)

### Stockage Partagé (API PHP)

**Endpoint** : `EXTERNAL_CONFIG_BASE_URL/config_api.php`

**Requête** :
```http
POST /config_api.php
Content-Type: application/json
X-API-Token: CONFIG_API_TOKEN

{
  "action": "get",
  "key": "magic_link_tokens"
}
```

**Avantages** :
- Partagé entre tous les workers Render
- Survit aux redeploys
- Centralisé avec le backend PHP existant

**Inconvénients** :
- Configuration supplémentaire requise
- Dépendance réseau vers l'API PHP

---

## API Endpoints

### Génération de Magic Link

```http
POST /api/auth/magic-link
Authorization: Session Flask-Login requise
Content-Type: application/json

{
  "unlimited": false  // true pour permanent, false pour usage unique
}
```

**Réponse** :
```json
{
  "success": true,
  "magic_link": "https://domain.com/dashboard/magic-link/abc123def456",
  "expires_at": "2026-01-19T12:15:00Z",
  "single_use": true
}
```

### Consommation de Magic Link

```http
GET /dashboard/magic-link/<token>
```

**Comportement** :
- Validation de la signature HMAC
- Vérification TTL (si usage unique)
- Création session Flask-Login
- Redirection vers `/dashboard`

**Réponses** :
- `302` → Redirection vers dashboard (succès)
- `404` → Token invalide ou expiré
- `410` → Token déjà utilisé (usage unique)

---

## Implémentation Technique

### Service MagicLinkService

**Méthodes principales** :

```python
class MagicLinkService:
    def generate_magic_link(self, unlimited=False) -> dict:
        """Génère un token et retourne le lien complet"""
        
    def validate_magic_link(self, token: str) -> dict:
        """Valide un token et retourne les informations"""
        
    def consume_magic_link(self, token: str) -> bool:
        """Marque un token comme utilisé (usage unique)"""
        
    def revoke_magic_link(self, token: str) -> bool:
        """Révoque manuellement un token"""
        
    def cleanup_expired_tokens(self) -> int:
        """Nettoie les tokens expirés"""
```

### Signature Cryptographique

**Algorithme** : HMAC SHA-256
**Clé** : `FLASK_SECRET_KEY`
**Payload** : `token_id + created_at + single_use`

```python
import hmac
import hashlib
import time

def generate_token():
    token_id = secrets.token_urlsafe(32)
    created_at = time.time()
    payload = f"{token_id}:{created_at}"
    signature = hmac.new(
        FLASK_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}:{signature}"
```

### Sécurité des Tokens

- **Entropie** : 32 octets aléatoires pour `token_id`
- **Timestamp** : Protection contre les attaques de rejeu
- **Signature** : Impossible de falsifier sans `FLASK_SECRET_KEY`
- **Validation** : Vérification stricte de la signature et du format

---

## Intégration UI

### Dashboard Integration

**Bouton de génération** :
```html
<button id="generateMagicLink" class="btn-primary">
  ✨ Générer un magic link
</button>

<div class="form-check">
  <input type="checkbox" id="unlimitedLink">
  <label for="unlimitedLink">Lien illimité (permanent)</label>
</div>
```

**JavaScript** :
```javascript
async function generateMagicLink() {
  const unlimited = document.getElementById('unlimitedLink').checked;
  
  const response = await fetch('/api/auth/magic-link', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ unlimited })
  });
  
  const data = await response.json();
  if (data.success) {
    copyToClipboard(data.magic_link);
    showCopiedFeedback();
  }
}
```

### Login Page Integration

**Champ Magic Token** :
```html
<div class="magic-link-section">
  <label>✨ Magic Token</label>
  <input type="text" id="magicToken" placeholder="Collez votre magic link ici">
  <button id="useMagicLink">Utiliser</button>
</div>
```

**Extraction du token** :
```javascript
function extractTokenFromUrl(url) {
  const match = url.match(/\/magic-link\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : null;
}
```

---

## Journalisation et Surveillance

### Logs Structurés

**Préfixe** : `MAGIC_LINK:*`

```text
MAGIC_LINK: Generated one-shot token for user admin (expires: 2026-01-19T12:15:00Z)
MAGIC_LINK: Generated permanent token for user admin
MAGIC_LINK: Consumed one-shot token abc123def456 (user: admin)
MAGIC_LINK: Validated permanent token xyz789uvw (user: admin)
MAGIC_LINK: Revoked token abc123def456 (user: admin)
MAGIC_LINK: Cleaned up 5 expired tokens
```

### Métriques de Surveillance

- **Tokens générés** : Par type (usage unique vs permanent)
- **Taux d'utilisation** : Tokens consommés / tokens générés
- **Durée de vie** : Temps moyen avant consommation
- **Échecs** : Tokens invalides, expirés, déjà utilisés

### Alertes

- **Génération excessive** : Plus de 10 tokens/heure par utilisateur
- **Taux d'échec élevé** : >50% d'échecs de validation
- **Tokens permanents** : Alertes sur les tokens permanents créés

---

## Bonnes Pratiques

### Sécurité

1. **Clé secrète robuste** : 64+ caractères aléatoires
2. **HTTPS obligatoire** : Jamais de magic links en HTTP
3. **TTL raisonnable** : 15-30 minutes pour usage unique
4. **Permissions fichiers** : `chmod 600` sur `magic_link_tokens.json`
5. **Rotation des clés** : Changer `FLASK_SECRET_KEY` périodiquement

### Usage

1. **Usage unique** : Préférer pour les accès temporaires
2. **Tokens permanents** : Révoquer régulièrement
3. **Audit** : Surveiller les logs d'utilisation
4. **Documentation** : Informer les utilisateurs du fonctionnement

### Maintenance

1. **Nettoyage automatique** : Exécuter `cleanup_expired_tokens()` quotidiennement
2. **Monitoring** : Surveiller la taille du fichier de tokens
3. **Backup** : Sauvegarder les tokens permanents si nécessaire
4. **Tests** : Valider les scénarios d'échec et de sécurité

---

## Dépannage

### Tokens Invalides

**Symptôme** : "Token invalide ou expiré"

**Causes possibles** :
- Token modifié/corrompu
- Signature HMAC invalide
- `FLASK_SECRET_KEY` changée entre génération et validation

**Solution** : Régénérer le token avec la même `FLASK_SECRET_KEY`

### Tokens Déjà Utilisés

**Symptôme** : "Token déjà utilisé"

**Cause** : Tentative de réutilisation d'un token à usage unique

**Solution** : Générer un nouveau token

### Problèmes de Stockage Partagé

**Symptôme** : Erreur de connexion à l'API PHP

**Causes possibles** :
- `EXTERNAL_CONFIG_BASE_URL` incorrect
- `CONFIG_API_TOKEN` invalide
- Réseau inaccessible

**Solution** : Vérifier la configuration et la connectivité réseau

---

## Tests

### Tests Unitaires

```python
def test_generate_magic_link():
    token = magic_link_service.generate_magic_link()
    assert 'magic_link' in token
    assert 'expires_at' in token

def test_validate_magic_link():
    token_data = magic_link_service.generate_magic_link()
    token = extract_token_from_url(token_data['magic_link'])
    
    validated = magic_link_service.validate_magic_link(token)
    assert validated['valid'] is True

def test_consume_one_shot_token():
    token_data = magic_link_service.generate_magic_link()
    token = extract_token_from_url(token_data['magic_link'])
    
    success = magic_link_service.consume_magic_link(token)
    assert success is True
    
    # Deuxième consommation doit échouer
    success = magic_link_service.consume_magic_link(token)
    assert success is False
```

### Tests d'Intégration

- **Flux complet** : Génération → Validation → Consommation
- **Stockage partagé** : API PHP disponible/indisponible
- **Scénarios d'erreur** : Token invalide, expiré, déjà utilisé
- **Performance** : Temps de génération et validation

---

*Cette documentation reflète l'état actuel du système d'authentification magic link avec support multi-workers et tokens permanents. Pour les détails d'implémentation, voir `services/magic_link_service.py`.*
