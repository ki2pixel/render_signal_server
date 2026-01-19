# Résilience & Architecture (Lot 2/3 - 2026-01-14)

## Vue d'ensemble

Le Lot 2 introduit des améliorations critiques de résilience pour garantir la stabilité du service en environnement de production, notamment sur Render multi-conteneurs et en cas de défaillances externes. Le Lot 3 complète avec des optimisations performance et validations anti-OOM.

---

## Lot 2 : Résilience Infrastructure

### Verrou Distribué Redis

### Implémentation
- **Fichier** : `background/lock.py`
- **Clé** : `render_signal:poller_lock`
- **TTL** : 5 minutes (300 secondes) par défaut
- **Token** : Inclusion du PID dans la valeur pour traçabilité

### Configuration
```bash
# Activer le verrou distribué (recommandé pour multi-conteneurs)
REDIS_URL=redis://user:pass@host:port/db

# TTL personnalisé (optionnel)
REDIS_LOCK_TTL_SECONDS=300
```

### Comportement
1. **Avec Redis** : Utilise `redis.set(key, value, nx=True, ex=TTL)` pour verrouillage distribué
2. **Sans Redis** : Fallback sur verrou fcntl traditionnel avec WARNING "Using file-based lock (unsafe for multi-container deployments)"
3. **Monitoring** : `redis-cli GET render_signal:poller_lock` pour vérifier l'état du verrou

### Tests
- **Fichier** : `tests/test_lock_redis.py`
- **Format** : Given/When/Then
- **Marqueur** : `@pytest.mark.redis`
- **Couverture** : Mocks Redis, validation TTL, gestion erreurs

## Fallback R2 Garanti

### Problème résolu
Avant le Lot 2, un échec de l'offload R2 pouvait interrompre tout le flux webhook.

### Solution
- **Conservation URLs** : Maintien explicite de `raw_url`/`direct_url` avant tentative R2
- **Try/except large** : Capture toutes les exceptions dans `request_remote_fetch()`
- **Log WARNING** : Journalisation des échecs mais continuation du flux
- **Timeouts adaptatifs** : 120s pour Dropbox `/scl/fo/`, 15s par défaut

### Implémentation dans `orchestrator.py`
```python
# Conservation URLs sources
fallback_raw_url = source_url
fallback_direct_url = link_item.get('direct_url') or source_url

try:
    r2_result = r2_service.request_remote_fetch(
        source_url=normalized_source_url,
        provider=provider,
        email_id=email_id,
        timeout=remote_fetch_timeout
    )
except Exception:
    r2_result = None
    # WARNING loggé mais flux continue avec URLs sources
```

### Bénéfices
- **Flux continu** : Les webhooks sont toujours envoyés même si R2 échoue
- **Économie maintenue** : Offload fonctionne quand disponible, fallback gracieux sinon
- **Traçabilité** : Logs WARNING pour monitoring des taux d'échec

## Watchdog IMAP Anti-Zombie

### Problème résolu
Les connexions IMAP pouvaient rester bloquées indéfiniment en cas de serveur défaillant.

### Solution
- **Timeout paramétrable** : `timeout=30` par défaut dans `create_imap_connection()`
- **Configuration** : Variable `IMAP_TIMEOUT_SECONDS` pour surcharge
- **Prévention** : Évite les threads bloqués et les zombies

### Configuration
```bash
# Timeout IMAP personnalisé (optionnel)
IMAP_TIMEOUT_SECONDS=30
```

### Implémentation
```python
def create_imap_connection(
    logger: Optional[Logger],
    timeout: int = 30,  # Paramétrable
) -> Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]]:
```

### Implémentation Technique

#### Verrou Redis (background/lock.py)
```python
# Clé et TTL
_REDIS_LOCK_KEY = "render_signal:poller_lock"
_REDIS_LOCK_TTL_SECONDS = 300

# Token avec PID
token = f"pid={os.getpid()}"
acquired = client.set(key, token, nx=True, ex=ttl)
```

#### Fallback R2 (orchestrator.py)
```python
# Conservation explicite du lien source
fallback_raw_url = source_url
try:
    r2_result = r2_service.request_remote_fetch(...)
except Exception:
    r2_result = None
    logger.warning("R2_TRANSFER: fallback to source URL")
# Flux continue avec fallback_raw_url
```

#### Watchdog IMAP (imap_client.py)
```python
# Timeout 30s sur toutes les opérations
imap_client.select('INBOX', timeout=30)
imap_client.search(None, criteria, timeout=30)
```

## Tests & Couverture

### Résultats Lot 2
- **Total tests** : 386 passed, 13 skipped, 0 failed
- **Couverture** : 70.12% (amélioration significative)
- **Nouveaux tests** : `test_lock_redis.py` avec validation complète

### Tests Redis Lock
```python
@pytest.mark.unit
def test_acquire_singleton_lock_uses_redis_when_redis_url_present():
    # Given: REDIS_URL is present and Redis SET returns True
    # When: acquiring the singleton lock
    # Then: Redis path is used and file lock is not created
```

## Configuration Complète

### Variables Lot 2
```bash
# Verrou distribué Redis
REDIS_URL=redis://user:pass@host:port/db
REDIS_LOCK_TTL_SECONDS=300

# Watchdog IMAP
IMAP_TIMEOUT_SECONDS=30
```

### Monitoring
- **Logs Redis** : "Using file-based lock (unsafe for multi-container deployments)"
- **Logs R2** : "R2_TRANSFER:*" pour succès/échecs
- **Logs IMAP** : Timeout et reconnexions automatiques

## Impact sur la Production

### Multi-conteneurs Render
- **Avant** : Risque de double polling avec fcntl
- **Après** : Verrou distribué garantit unicité

### Fiabilité R2
- **Avant** : Échec R2 = interruption webhook
- **Après** : Fallback transparent avec URLs sources

### Stabilité IMAP
- **Avant** : Connexions zombies possibles
- **Après** : Timeout garanti et reconnexion automatique

## Checklist de Mise en Production

- [ ] `REDIS_URL` configuré pour multi-conteneurs
- [ ] Tests verrou Redis validés en environnement de test
- [ ] Timeout IMAP 30s testé avec serveur de production
- [ ] Fallback R2 validé (simuler échec Worker)
- [ ] Monitoring des logs WARNING mis en place
- [ ] Documentation opératoire mise à jour

---

## Lot 3 : Performance & Validation (2026-01-14)

### Anti-OOM Parsing HTML

#### Problème résolu
Les emails HTML volumineux (plusieurs MB) pouvaient provoquer des OOM kills sur les conteneurs Render avec 512MB de RAM.

#### Solution
- **Limite stricte** : Troncature du contenu `text/html` à 1MB avant parsing
- **Log WARNING** : "HTML content truncated (exceeded 1MB limit)" pour traçabilité
- **Parsing sécurisé** : BeautifulSoup opère sur contenu limité

#### Implémentation dans `orchestrator.py`
```python
MAX_HTML_BYTES = 1024 * 1024  # 1MB

def _extract_text_from_html(html_content: str) -> str:
    if len(html_content.encode('utf-8')) > MAX_HTML_BYTES:
        logger.warning("HTML content truncated (exceeded 1MB limit)")
        html_content = html_content[:MAX_HTML_BYTES]
    # Parsing BeautifulSoup sur contenu tronqué
```

### Tests Résilience R2

#### Objectif
Valider que le fallback R2 fonctionne correctement même en cas d'échec total du Worker.

#### Implémentation
- **Fichier** : `tests/test_r2_resilience.py`
- **Scénarios** : Exception levée, retour None, timeout
- **Validation** : Webhook envoyé avec URLs sources, `r2_url` absent/None

#### Tests Given/When/Then
```python
@pytest.mark.integration
def test_r2_resilience_worker_down_continues_flow():
    # Given: R2 service configured but worker throws exception
    # When: Processing email with delivery links
    # Then: Webhook sent with raw_url, r2_url is None
```

### Résultats Lot 3

- **Total tests** : 389 passed, 13 skipped, 0 failed
- **Couverture** : Maintenue à ~70%
- **Nouveaux tests** : `test_r2_resilience.py` avec scénarios complets

### Configuration Lot 3

```bash
# Limite HTML (déjà intégrée, pas de variable ENV nécessaire)
# MAX_HTML_BYTES = 1048576  # 1MB (hardcodé pour sécurité)
```

### Monitoring Lot 3

- **Logs HTML** : "HTML content truncated (exceeded 1MB limit)"
- **Logs R2** : "R2_TRANSFER:*" avec fallback explicite
- **Métriques** : Taux de troncature HTML, taux d'échec R2

---

## Synthèse Lot 2/3

### Bénéfices Combinés

1. **Stabilité Infrastructure** : Verrou Redis + watchdog IMAP
2. **Résilience External** : Fallback R2 garanti + timeouts robustes
3. **Performance Optimisée** : Anti-OOM + parsing sécurisé
4. **Tests Complets** : Couverture tous les scénarios de défaillance

### Impact Production

| Aspect | Avant Lot 2/3 | Après Lot 2/3 |
|--------|---------------|---------------|
| Multi-conteneurs | Risque double polling | Verrou distribué garanti |
| Worker R2 down | Interruption webhook | Fallback transparent |
| Emails volumineux | OOM possible | Troncation 1MB sécurisée |
| Connexions IMAP | Zombies possibles | Timeout 30s garanti |
| Monitoring | Logs limités | Traçabilité complète |

### Checklist Finale

- [ ] Lot 2 : Redis lock activé (`REDIS_URL`)
- [ ] Lot 2 : Timeout IMAP 30s validé
- [ ] Lot 2 : Fallback R2 testé
- [ ] Lot 3 : Tests résilience R2 validés
- [ ] Lot 3 : Monitoring troncature HTML
- [ ] Documentation complète mise à jour
- [ ] Équipe production formée aux nouveaux logs
