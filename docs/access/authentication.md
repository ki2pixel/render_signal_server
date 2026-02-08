# Authentication

**TL;DR**: On utilise des magic links signés HMAC pour l'accès sans mot de passe. Les tokens peuvent être à usage unique (15min par défaut) ou permanents, avec stockage partagé entre workers Render.

---

## Le problème : les mots de passe qui ne sont pas pratiques

J'ai hérité d'un système avec authentification par mot de passe. Les problèmes étaient multiples :

- **Support** : Les utilisateurs oublient leurs mots de passe
- **Sécurité** : Mots de passe faibles ou partagés
- **Maintenance** : Réinitialisation fréquente des mots de passe
- **UX** : Champ de mot de passe dans le formulaire de login

Pire encore : sur Render multi-conteneurs, chaque instance avait sa propre session, rendant l'authentification incohérente.

---

## La solution : badges d'accès cryptographiques

Pensez aux magic links comme des badges d'accès temporaires ou permanents pour un bâtiment sécurisé. Chaque badge est signé cryptographiquement, peut être à usage unique (visiteur) ou permanent (résident), et fonctionne sur toutes les entrées (multi-conteneurs).

### ❌ L'ancien monde : clés physiques partagées

```python
# ANTI-PATTERN - login.html
<form method="post">
  <input type="password" name="password" placeholder="Mot de passe">
  <button type="submit">Se connecter</button>
</form>

# ANTI-PATTERN - auth/user.py
class User(UserMixin):
    def verify_password(self, password):
        return password == stored_password  # Comparaison en clair !
```

### ✅ Le nouveau monde : badges HMAC signés

```python
# services/magic_link_service.py
class MagicLinkService:
    def generate_magic_link(self, unlimited=False) -> dict:
        """Génère un token signé HMAC"""
        token_id = secrets.token_urlsafe(32)
        created_at = time.time()
        expires_at = created_at + (TTL_INFINITE if unlimited else self.ttl_seconds)
        
        # Signature HMAC SHA-256
        payload = f"{token_id}:{created_at}"
        signature = hmac.new(
            FLASK_SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'magic_link': f"https://domain.com/dashboard/magic-link/{token_id}:{signature}",
            'expires_at': datetime.fromtimestamp(expires_at).isoformat() if expires_at else None,
            'single_use': not unlimited,
            'created_at': datetime.fromtimestamp(created_at).isoformat()
        }
    
    def validate_magic_link(self, token: str) -> dict:
        """Valide un token HMAC"""
        try:
            token_id, created_at, signature = token.split(':')
            payload = f"{token_id}:{created_at}"
            expected_signature = hmac.new(
                FLASK_SECRET_KEY.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
            
            is_valid = hmac.compare_digest(signature.encode(), expected_signature.encode())
            created_at_timestamp = float(created_at)
            
            # Validation TTL
            if not self.unlimited and created_at_timestamp < time.time():
                return {'valid': False, 'error': 'Token expired'}
            
            return {'valid': is_valid, 'token_id': token_id}
            
        except (ValueError, IndexError) as e:
            return {'valid': False, 'error': f'Invalid token format: {e}'}
```

**Le gain** : zéro mot de passe, badges sécurisés, et accès multi-entrées comme dans un bâtiment moderne.

---

## Architecture : badges avec système de contrôle central

### Flux complet

```
Dashboard UI → MagicLinkService → Badge Store → Flask-Login → Accès Dashboard
```

### 1. MagicLinkService (Singleton)

```python
# services/magic_link_service.py
class MagicLinkService:
    def __init__(self):
        self.ttl_seconds = int(os.environ.get('MAGIC_LINK_TTL_SECONDS', 900))  # 15min
        self.tokens_file = os.environ.get('MAGIC_LINK_TOKENS_FILE', './magic_link_tokens.json')
        self.external_config_base_url = os.environ.get('EXTERNAL_CONFIG_BASE_URL')
        self.config_api_token = os.environ.get('CONFIG_API_TOKEN')
        self.config_api_storage_dir = os.environ.get('CONFIG_API_STORAGE_DIR')
        
        # Verrouillage du fichier de tokens
        self._ensure_tokens_file_locked()
    
    def _ensure_tokens_file_locked(self):
        """Crée et verrouille le fichier de tokens"""
        if not os.path.exists(self.tokens_file):
            with open(self.tokens_file, 'w') as f:
                json.dump({}, f)
        
        # Verrouillage via fcntl
        with open(self.tokens_file, 'r+') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                existing = json.load(f)
                json.dump(existing, f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

### 2. Stockage partagé via API PHP

```php
// deployment/config/config_api.php
class ConfigAPI {
    private function get_magic_link_tokens(): array {
        $file = $this->storage_dir . '/magic_link_tokens.json';
        if (!file_exists($file)) {
            return [];
        }
        return json_decode(file_get_contents($file), true);
    }
    
    private function save_magic_link_tokens(array $tokens): void {
        $file = $this->storage_dir . '/magic_link_tokens.json';
        $json = json_encode($tokens, JSON_PRETTY_PRINT);
        file_put_contents($file, $json, LOCK_EX);
    }
    
    // Endpoint POST /config_api.php?action=get&key=magic_link_tokens
    public function handle_get_magic_link_tokens(): array {
        return $this->get_magic_link_tokens();
    }
    
    // Endpoint POST /config_api.php?action=set&key=magic_link_tokens
    public function handle_set_magic_link_tokens(array $tokens): bool {
        $this->save_magic_link_tokens($tokens);
        return true;
    }
}
```

### 3. Intégration Flask-Login

```python
# auth/helpers.py
@login_required
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
```

---

## Configuration : variables essentielles

### Variables obligatoires

```bash
# Clé secrète pour signatures HMAC (64+ caractères recommandé)
FLASK_SECRET_KEY=votre-clé-secrète-très-robuste

# Durée de vie par défaut (15 minutes)
MAGIC_LINK_TTL_SECONDS=900
```

### Variables optionnelles (stockage partagé)

```bash
# API PHP pour stockage partagé entre workers
EXTERNAL_CONFIG_BASE_URL=https://votre-domaine.tld
CONFIG_API_TOKEN=token-hmac-partagé-entre-Render-et-PHP
CONFIG_API_STORAGE_DIR=/home/user/data/app_config

# Fichier local fallback
MAGIC_LINK_TOKENS_FILE=./magic_link_tokens.json
```

---

## Idées reçues sur les badges d'accès

### ❌ "Les tokens permanents sont moins sûrs"
Les badges permanents utilisent la même signature HMAC que les badges temporaires. La différence est seulement l'absence d'expiration, pas une moindre sécurité cryptographique.

### ❌ "Le TTL par défaut de 15 minutes est trop court"
Le TTL est configurable via `MAGIC_LINK_TTL_SECONDS`. 15 minutes est un équilibre entre sécurité et UX pour les accès temporaires (support, mobile).

### ❌ "L'API PHP complique la sécurité"
L'API PHP utilise le même token `CONFIG_API_TOKEN` que toutes les autres configurations. C'est une extension du système de stockage partagé, pas une surface d'attaque supplémentaire.

---

## Tableau des modes d'accès

| Mode | TTL | Usage idéal | Risques | Stockage | Révocation |
|------|-----|-------------|----------|----------|------------|
| One-shot | 15min (configurable) | Support, mobile ponctuel | Faible (auto-expiration) | Volatil | Automatique |
| Permanent | Illimité | Admin, accès fréquent | Moyen (révocation manuelle) | Persistant | Manuelle |
| Session Flask | Variable | Navigation continue | Faible (session side) | Session | Déconnexion |

---

## Modes d'utilisation : visiteur vs résident

### Badges visiteur (One-Shot)

**Idéal pour** :
- Accès temporaires
- Partages ponctuels
- Support technique
- Accès mobile sécurisé

```python
# Génération badge visiteur
token_data = magic_link_service.generate_magic_link(unlimited=False)

# URL générée
# https://domain.com/dashboard/magic-link/abc123def456:signature

# Auto-révocation après 15 minutes
# Le badge expire automatiquement
```

### Badges résident (Permanents)

**Idéal pour** :
- Accès fréquents
- Administrateurs système
- Accès depuis mobile permanent
- Intégrations continues

```python
# Génération badge résident
token_data = magic_link_service.generate_magic_link(unlimited=True)

# URL permanente
# https://domain.com/dashboard/magic-link/xyz789uvw:signature

# Pas d'expiration
# Le badge reste valide jusqu'à révocation manuelle
```

---

## Sécurité cryptographique

### Signature HMAC SHA-256

```python
import hmac
import hashlib
import time
import secrets

def generate_hmac_signature():
    """Génère une signature HMAC SHA-256"""
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

### Validation stricte

```python
def validate_hmac_signature(token, expected_signature):
    """Validation timing-attack resistant"""
    try:
        token_id, created_at, signature = token.split(':')
        payload = f"{token_id}:{created_at}"
        expected = hmac.new(
            FLASK_SECRET_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison
        return hmac.compare_digest(signature.encode(), expected.encode())
    except (ValueError, IndexError):
        return False
    
    return True
```

### Protection contre les attaques

- **Timing attacks** : Comparaison constante temps (`hmac.compare_digest`)
- **Replay attacks** : Timestamp dans la payload
- **Brute force** : Entropie des tokens 32 octets
- **Key rotation** : Changer `FLASK_SECRET_KEY` régulièrement

---

## Intégration UI : dashboard et login

### Dashboard : génération de magic links

```html
<!-- dashboard.html -->
<div class="magic-link-section">
    <h3>✨ Accès Rapide</h3>
    
    <div class="form-check">
        <input type="checkbox" id="unlimitedLink">
        <label for="unlimitedLink">Lien permanent (illimité)</label>
    </div>
    
    <button id="generateMagicLink" class="btn btn-primary">
        ✨ Générer un magic link
    </button>
    
    <div id="magicLinkResult" class="mt-3"></div>
</div>
```

### JavaScript : orchestration ES6

```javascript
// static/dashboard.js
import { ApiService } from './services/ApiService.js';

class MagicLinkManager {
    async generateMagicLink(unlimited = false) {
        const response = await ApiService.post('/api/auth/magic-link', {
            unlimited
        });
        
        const data = await response.json();
        
        if (data.success) {
            this.copyToClipboard(data.magic_link);
            this.showSuccessMessage('Magic link copié !');
        }
    }
    
    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showSuccessMessage('Lien copié dans le presse-papiers');
        }).catch(err => {
            this.showErrorMessage('Erreur de copie');
        });
    }
    
    showSuccessMessage(message) {
        // Affiche le message de succès
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.className = 'toast success';
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}
```

### Login page : champ magic token

```html
<!-- login.html -->
<div class="magic-link-section">
    <p>✨ Ou utilisez un magic link</p>
    <div class="form-group">
        <label for="magicToken">✨ Magic Token</label>
        <input type="text" id="magicToken" placeholder="Collez votre magic link ici">
        <button id="useMagicLink">Utiliser</button>
    </div>
</div>
```

---

## API REST : endpoints sécurisés

### Génération de magic link

```http
POST /api/auth/magic-link
Authorization: Session Flask-Login requis
Content-Type: application/json

{
  "unlimited": false
}
```

**Réponse** :
```json
{
  "success": true,
  "magic_link": "https://domain.com/dashboard/magic-link/abc123def456:signature",
  "expires_at": "2026-02-04T12:15:00Z",
  "single_use": true
}
```

### Consommation de magic link

```http
GET /dashboard/magic-link/abc123def456:signature
```

**Comportement** :
- Validation du token
- Vérification TTL (si usage unique)
- Création session Flask-Login
- Redirection vers dashboard

---

## Stockage partagé : multi-workers Render

### Architecture Redis-first

```python
# config/app_config_store.py
class AppConfigStore:
    def get_magic_link_tokens(self) -> list:
        # 1. Essai Redis
        if self._redis_client:
            try:
                data = self._redis_client.get("r:ss:magic_link_tokens:v1")
                if data:
                    return json.loads(data)
            except RedisError:
                logger.warning("Redis unavailable for magic link tokens, using file fallback")
        
        # 2. Fallback API PHP
        if self.external_config_base_url:
            try:
                response = requests.post(
                    f"{self.external_config_base_url}/config_api.php",
                    json={"action": "get", "key": "magic_link_tokens"},
                    headers={"X-API-Token": self.config_api_token},
                    timeout=10
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Failed to fetch magic link tokens from API: {e}")
        
        # 3. Fallback fichier local
        return self._load_from_file("magic_link_tokens.json")
```

### Synchronisation automatique

```python
# services/magic_link_service.py
def save_magic_link_token(token_data):
    """Sauvegarde un token avec synchronisation"""
    
    # 1. Persistance locale
    self._save_token_to_file(token_data)
    
    # 2. Synchronisation API PHP si disponible
    if self.external_config_base_url:
        try:
            current_tokens = self._load_tokens_from_file()
            requests.post(
                f"{self.external_config_base_url}/config_api.php",
                json={"action": "set", "key": "magic_link_tokens", "tokens": current_tokens},
                headers={"X-API-Token": self.config_api_token},
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to sync magic link tokens to API: {e}")
```

---

## Monitoring : logs et métriques

### Logs structurés

```bash
# Logs avec préfixe MAGIC_LINK
MAGIC_LINK: Generated one-shot token for user admin (expires: 2026-02-04T12:15:00Z)
MAGIC_LINK: Generated permanent token for user admin
MAGIC_LINK: Consumed one-shot token abc123def456 (user: admin)
MAGIC_LINK: Validated permanent token xyz789uvw (user: admin)
MAGIC_LINK: Revoked token abc123def456 (user: admin)
MAGIC_LINK: Cleaned up 5 expired tokens
```

### Métriques à surveiller

| Métrique | Seuil | Action |
|----------|-------|--------|
| Taux d'échec validation | > 10% | Vérifier `FLASK_SECRET_KEY` |
| Tokens permanents créés | > 5/jour | Vérifier politique d'usage |
| Durée vie moyenne | < 5min | Vérifier TTL par défaut |

### Alertes recommandées

```bash
# Alerte si génération excessive
if [ $(curl -s https://render-signal-server-latest.onrender.com/api/webhook_logs?days=1 | jq '.logs | grep -c "MAGIC_LINK.*Generated" | wc -l) -gt 10 ]; then
    echo "ALERT: Excessive magic link generation detected"
fi

# Alerte si taux d'échec > 50%
error_rate=$(curl -s https://render-signal-server-latest.onrender.com/api/webhook_logs?days=1 | jq '.logs | grep '"status":"error"' | wc -l | tail -n | jq '.logs | length | wc -l') / total * 100)
if ((error_rate > 50)); then
    echo "ALERT: High webhook error rate detected: ${error_rate}%"
fi
```

---

## Tests : couverture complète

### Tests unitaires

```python
# tests/test_magic_link_service.py
def test_generate_magic_link_one_shot():
    """Test génération token usage unique"""
    service = MagicLinkService()
    result = service.generate_magic_link(unlimited=False)
    
    assert 'magic_link' in result
    assert result['single_use'] is True
    assert 'expires_at' in result

def test_generate_magic_link_permanent():
    """Test génération token permanent"""
    service = MagicLinkService()
    result = service.generate_magic_link(unlimited=True)
    
    assert result['single_use'] is False
    assert 'expires_at' is None

def test_validate_magic_link():
    """Test validation HMAC"""
    service = MagicLinkService()
    
    # Token valide
    valid_token = service.generate_magic_link()
    token = valid_token['magic_link'].split(':')[-1]
    validation = service.validate_magic_link(token)
    
    assert validation['valid'] is True
    
    # Token invalide
    invalid_token = "invalid_token_format"
    validation = service.validate_magic_link(invalid_token)
    assert validation['valid'] is False
```

### Tests d'intégration

```python
# tests/test_auth_magic_link.py
def test_magic_link_flow_complete():
    """Test flux complet : génération → validation → consommation"""
    service = MagicLinkService()
    
    # 1. Génération
    token_data = service.generate_magic_link(unlimited=False)
    token = token_data['magic_link'].split(':')[-1]
    
    # 2. Validation
    validation = service.validate_magic_link(token)
    assert validation['valid'] is True
    
    # 3. Consommation
    success = service.consume_magic_link(token)
    assert success is True
    
    # 4. Double consommation doit échouer
    success2 = service.consume_magic_link(token)
    assert success2 is False
```

### Commande d'exécution

```bash
# Tests magic link complets
pytest tests/test_magic_link_service.py tests/test_auth_magic_link.py -v

# Tests avec marqueur webhook
pytest -m "webhook" -v

# Tests résilience Redis
pytest -m "resilience" -v
```

---

## La Golden Rule : Badges HMAC signés, stockage partagé, fallback garanti

Les magic links sont des badges d'accès cryptographiques signés HMAC avec `FLASK_SECRET_KEY`. Le stockage est partagé entre workers via API PHP avec fallback fichier local. Les badges peuvent être visiteur (15min TTL par défaut) ou résident (permanent). La validation est timing-attack resistant avec `hmac.compare_digest`. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la sécurité du bâtiment.

---

*Pour les détails d'API : voir `docs/v2/core/configuration-reference.md`. Pour l'intégration UI : voir `docs/v2/access/dashboard-ui.md`.*
