# Magic Link Authentication

**TL;DR**: On génère des tokens HMAC signés pour authentification sans mot de passe, stockés Redis-first avec fallback fichier, usage unique par défaut et TTL configurable pour sécuriser l'accès dashboard sans gérer de mots de passe.

---

## Le problème : authentification lourde pour accès occasionnel

J'ai hérité d'un système où l'accès au dashboard nécessitait soit des identifiants fixes (username/password), soit une gestion complexe de sessions. Le problème ? Les utilisateurs avaient besoin d'un accès simple et sécurisé sans la lourdeur des mots de passe, et les tokens temporaires devaient être révoquables en cas de compromission.

---

## La solution : magic links signés avec stockage hybride

Pensez aux magic links comme des clés électroniques temporaires : chaque lien contient un token HMAC signé dérivé de `FLASK_SECRET_KEY`, stocké en Redis pour la performance avec fallback fichier pour la persistance, et marqué comme "consommé" après usage pour éviter les réutilisations. Le système nettoie automatiquement les tokens expirés.

### ❌ L'ancien monde : mots de passe statiques ou sessions complexes

```python
# ANTI-PATTERN - authentification par mot de passe
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    if username == "admin" and password == "secret123":
        session["user"] = username
        return redirect("/dashboard")
```

### ✅ Le nouveau monde : tokens signés auto-nettoyants

```python
# routes/api_auth.py - génération
@login_required
def create_magic_link():
    unlimited = request.json.get("unlimited", False)
    token, expires_at = magic_link_service.generate_token(unlimited=unlimited)
    magic_link = url_for("dashboard.consume_magic_link_token", token=token, _external=True)
    return jsonify({"magic_link": magic_link, "expires_at": expires_at})

# routes/dashboard.py - consommation
def consume_magic_link_token(token):
    success, username = magic_link_service.consume_token(token)
    if success:
        login_user(create_user(username))
        return redirect("/dashboard")
    return redirect("/login?error=Token invalide")
```

**La révolution** : signature HMAC + stockage hybride + nettoyage automatique.

---

## Architecture du système de magic links

### Token signé HMAC-SHA256

```python
# services/magic_link_service.py
def _sign_components(self, token_id: str, expires_component: str) -> str:
    payload = f"{token_id}.{expires_component}".encode("utf-8")
    return hmac_new(self._secret_key, payload, sha256).hexdigest()

def generate_token(self, *, unlimited: bool = False) -> Tuple[str, Optional[datetime]]:
    token_id = secrets.token_urlsafe(16)  # 128 bits d'entropie
    expires_component = "permanent" if unlimited else str(int(expires_at.timestamp()))
    
    signature = self._sign_components(token_id, expires_component)
    token = f"{token_id}.{expires_component}.{signature}"
    
    return token, expires_at if not unlimited else None
```

**Format** : `token_id.expires_component.signature`

### Stockage hybride Redis-first

```python
# Singleton avec configuration automatique
@classmethod
def get_instance(cls, **kwargs) -> "MagicLinkService":
    if cls._instance is None:
        kwargs = {
            "secret_key": settings.FLASK_SECRET_KEY,
            "storage_path": settings.MAGIC_LINK_TOKENS_FILE,
            "ttl_seconds": settings.MAGIC_LINK_TTL_SECONDS,
            "config_service": ConfigService(),
            "external_store": app_config_store,  # Redis
        }
        cls._instance = cls(**kwargs)
    return cls._instance
```

**Priorité** : Redis (performance) → Fichier (persistance) → Mémoire (fallback).

### Records avec métadonnées complètes

```python
@dataclass
class MagicLinkRecord:
    expires_at: Optional[float]     # Timestamp expiration
    consumed: bool = False         # Déjà utilisé ?
    consumed_at: Optional[float] = None  # Quand utilisé
    single_use: bool = True        # Usage unique par défaut
```

### Validation stricte et sécurisée

```python
def consume_token(self, token: str) -> Tuple[bool, str]:
    parts = token.split(".")
    if len(parts) != 3:
        return False, "Format invalide"
    
    token_id, expires_str, provided_sig = parts
    expected_sig = self._sign_components(token_id, expires_str)
    
    if not compare_digest(provided_sig, expected_sig):
        return False, "Signature invalide"
    
    # Vérifications temporelles et d'usage
    now = time.time()
    if expires_at and expires_at < now:
        return False, "Token expiré"
    
    record = state.get(token_id)
    if record.single_use and record.consumed:
        return False, "Token déjà utilisé"
    
    # Marquage consommation
    if record.single_use:
        record.consumed = True
        record.consumed_at = now
    
    return True, username
```

---

## Modes d'utilisation : limité vs illimité

### Tokens temporaires (défaut)

```python
# TTL configurable via settings.MAGIC_LINK_TTL_SECONDS
token, expires_at = service.generate_token(unlimited=False)
# expires_at = now + timedelta(seconds=ttl_seconds)
# single_use = True
```

**Usage** : Accès ponctuel sécurisé, expiration automatique.

### Tokens permanents (illimités)

```python
# Pour accès privilégié prolongé
token, expires_at = service.generate_token(unlimited=True)
# expires_at = None
# single_use = False (réutilisable)
```

**Usage** : Accès administrateur de longue durée.

---

## Sécurité : couches de protection

### Signature HMAC inviolable

```python
# Dérivée de FLASK_SECRET_KEY (clé secrète 256+ bits)
secret_key = settings.FLASK_SECRET_KEY.encode("utf-8")
signature = hmac_new(secret_key, payload, sha256).hexdigest()

# Vérification résistante aux timing attacks
if not compare_digest(provided_sig, expected_sig):
    return False, "Signature invalide"
```

### Usage unique renforcé

```python
# Double vérification : signature + état
if record.single_use and record.consumed:
    return False, "Token déjà utilisé"

# Marquage atomique avec verrouillage
with self._file_lock:
    record.consumed = True
    record.consumed_at = time.time()
    self._save_state(state)
```

### Nettoyage automatique des expirés

```python
def _cleanup_expired_tokens(self):
    now = time.time()
    for token_id, record in list(state.items()):
        if (record.expires_at and record.expires_at < now - 60) or \
           (record.consumed and record.consumed_at and record.consumed_at < now - 60):
            del state[token_id]  # Suppression sécurisée
```

---

## API REST : génération et révocation

### Génération de token

```http
POST /api/auth/magic-link
Authorization: Bearer <session_token>
Content-Type: application/json

{
  "unlimited": false  // optionnel, défaut false
}
```

**Réponse** :
```json
{
  "success": true,
  "magic_link": "https://app.com/login/magic/abc123.def456.ghi789",
  "expires_at": "2026-02-21T12:30:00Z",
  "unlimited": false
}
```

### Consommation via URL

```http
GET /login/magic/{token}
```

**Flux** :
1. Validation token
2. Création session utilisateur
3. Redirection vers dashboard

### Révocation

```python
# Suppression individuelle
service.revoke_token(token_id)

# Suppression totale (urgence sécurité)
service.revoke_all_tokens()
```

---

## Stockage et persistance

### Hiérarchie de stockage

| Priorité | Store | Avantages | Inconvénients |
|----------|-------|-----------|---------------|
| 1 | Redis | Performance, partage multi-conteneurs | Volatile |
| 2 | Fichier JSON | Persistance, atomicité | I/O lent |
| 3 | Mémoire | Rapidité absolue | Perte au restart |

### Fichier avec verrouillage inter-processus

```python
@contextmanager
def _interprocess_file_lock(self):
    lock_path = self._storage_path.with_suffix(".lock")
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)  # Verrou exclusif
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
```

### Atomicité des écritures

```python
def _save_state_to_file(self, serializable: dict):
    tmp_path = self._storage_path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, sort_keys=True)
    os.replace(tmp_path, self._storage_path)  # Atomic move
```

---

## Monitoring et observabilité

### Logs structurés

```python
# Génération
logger.info("MAGIC_LINK: token %s generated (expires_at=%s)", 
           token_id, expires_at.isoformat())

# Consommation
logger.info("MAGIC_LINK: token %s consumed by %s", token_id, username)

# Révocation
logger.info("MAGIC_LINK: token %s revoked", token_id)
logger.info("MAGIC_LINK: all tokens revoked")
```

### Métriques recommandées

- **Tokens générés par heure** : Activité utilisateur
- **Taux de succès consommation** : % tokens valides utilisés
- **Tokens expirés nettoyés** : Efficacité nettoyage
- **Erreurs validation** : Tentatives attaque

### Alertes sécurité

- **Tokens invalides > 10/minute** : Attaque par déni
- **Révocation massive** : Compromission détectée
- **Échec stockage Redis** : Problème infrastructure

---

## Tests : couverture sécurité

### 12 tests couvrant tous les scénarios

```bash
pytest tests/ -k "magic_link" -v
# test_magic_link_service.py: 8 tests
# test_api_auth.py: 4 tests
```

### Tests de sécurité critiques

```python
def test_token_signature_validation():
    """Signature HMAC ne peut pas être forgée"""
    # Token avec signature modifiée
    tampered_token = original_token.replace(signature, "fake")
    success, msg = service.consume_token(tampered_token)
    assert success == False
    assert "Signature invalide" in msg

def test_single_use_enforcement():
    """Token ne peut être utilisé qu'une fois"""
    success1, _ = service.consume_token(valid_token)
    success2, msg = service.consume_token(valid_token)
    
    assert success1 == True
    assert success2 == False
    assert "déjà utilisé" in msg
```

---

## Configuration requise

### Variables d'environnement

```bash
# Obligatoire
FLASK_SECRET_KEY=your-256-bit-secret-key-here

# Optionnel (défauts dans settings.py)
MAGIC_LINK_TTL_SECONDS=3600  # 1 heure
MAGIC_LINK_TOKENS_FILE=/path/to/tokens.json
```

### Permissions système

- **Redis** : `config:magic_link_tokens` (lecture/écriture)
- **Fichier** : Écriture dans répertoire data
- **Lock** : `fcntl` disponible (Linux/Unix)

---

## Évolutions prévues (Q2 2026)

### Sécurité renforcée

- **Signature Ed25519** : Remplacement HMAC par signatures asymétriques
- **Rate limiting** : Limitation génération par IP/utilisateur
- **Audit trail** : Historique complet des utilisations

### Fonctionnalités avancées

- **Tokens groupés** : Liens pour équipes entières
- **Expiration conditionnelle** : TTL basé sur événements
- **Réutilisation contrôlée** : Limite nombre d'usages

### Performance

- **Cache Redis distribué** : Partage entre instances
- **Compression stockage** : Tokens compacts pour gros volumes
- **Batch operations** : Génération/révocation multiples

---

## La Golden Rule : Signature HMAC, stockage hybride, usage unique

Les magic links utilisent une signature HMAC inviolable dérivée de la clé secrète, stockent l'état en Redis avec fallback fichier sécurisé, appliquent l'usage unique par défaut avec TTL configurable, et nettoient automatiquement les tokens expirés pour maintenir la sécurité sans complexité opérationnelle.

Token généré = signature vérifiée = session créée = accès sécurisé.
