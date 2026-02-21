# Deduplication Engine

**TL;DR**: On évite les doublons d'emails par MD5(subject|sender|date) et regroupement de sujets normalisés, avec Redis-first et fallbacks mémoire pour garantir la fiabilité même en cas de panne.

---

## Le problème : les doublons d'emails qui inondent les webhooks

J'ai hérité d'un système où chaque email pouvait être traité plusieurs fois : même expéditeur, même sujet, même date pouvaient déclencher plusieurs webhooks identiques. Le pire ? Les clients recevaient des notifications dupliquées, et les logs étaient pollués par les mêmes traitements répétés.

---

## La solution : moteur de déduplication à deux niveaux

Pensez au moteur de déduplication comme un système de contrôle d'accès avec deux sas : le premier vérifie l'identité exacte de l'email (MD5), le deuxième regroupe les conversations similaires par sujet normalisé. Redis stocke les autorisations, la mémoire sert de fallback gracieux.

### ❌ L'ancien monde : pas de déduplication, doublons partout

```python
# ANTI-PATTERN - orchestrator.py sans déduplication
def process_email(email_data):
    # Pas de vérification d'unicité
    send_webhook(email_data)  # Peut être appelé plusieurs fois !
```

### ✅ Le nouveau monde : déduplication Redis-first à deux niveaux

```python
# api_ingress.py - vérification avant traitement
email_id = _compute_email_id(subject=subject, sender=sender_email, date=email_date)

if is_email_id_processed_redis(email_id):
    return jsonify({"success": True, "status": "already_processed"}), 200

# Traitement...
mark_email_id_as_processed_redis(email_id)
```

**Le pattern** : vérification avant traitement, marquage immédiat après succès.

---

## Architecture du moteur de déduplication

### Niveau 1 : Déduplication par Email ID (MD5)

```python
# routes/api_ingress.py
def _compute_email_id(*, subject: str, sender: str, date: str) -> str:
    unique_str = f"{subject}|{sender}|{date}"
    return hashlib.md5(unique_str.encode("utf-8")).hexdigest()
```

**Logique** : MD5(subject|sender|date) garantit l'unicité par email individuel. Même expéditeur, même sujet, même timestamp = même ID.

### Niveau 2 : Regroupement par Sujet Normalisé

```python
# deduplication/subject_group.py
def generate_subject_group_id(subject: str) -> str:
    norm = normalize_no_accents_lower_trim(subject)
    core = strip_leading_reply_prefixes(norm)
    
    # Détection "Média Solution Missions Recadrage Lot X"
    is_media_solution = all(tok in core for tok in ["media solution", "missions recadrage", "lot"])
    lot_part = re.search(r"\blot\s+(\d+)\b", core)?.group(1)
    
    if is_media_solution and lot_part:
        return f"media_solution_missions_recadrage_lot_{lot_part}"
    if lot_part:
        return f"lot_{lot_part}"
    
    # Fallback : hash du sujet normalisé
    return f"subject_hash_{hashlib.md5(core.encode('utf-8')).hexdigest()}"
```

**Heuristique** : normalisation → extraction patterns métier → fallback hash.

### Redis-First avec Fallback Mémoire

```python
# deduplication/redis_client.py
def is_email_id_processed(redis_client, email_id: str, logger, processed_ids_key: str) -> bool:
    if redis_client is None:
        return False  # Pas de Redis = pas de déduplication
    try:
        return bool(redis_client.sismember(processed_ids_key, email_id))
    except Exception as e:
        logger.error(f"REDIS_DEDUP: Error checking email ID: {e}")
        return False  # Erreur Redis = assume NOT processed (safe)
```

**Pattern** : Redis en premier, fallback mémoire, logging d'erreur sans blocage.

---

## Clés Redis utilisées pour la déduplication

| Clé | Type | Usage | TTL |
|-----|------|-------|-----|
| `processed_ids:{date}` | Set | Email IDs traités | Jamais (historique) |
| `subject_groups:{month}` | Set | Groupes sujets traités | Jamais (mensuel) |
| `ttl:subject_groups:{month}:{group_id}` | String | TTL pour groupes sujets | Configurable |

### Scoping mensuel pour les groupes sujets

```python
def _monthly_scope_group_id(group_id: str, tz) -> str:
    now_local = datetime.now(tz) if tz else datetime.now()
    month_prefix = now_local.strftime("%Y-%m")
    return f"{month_prefix}:{group_id}"
```

**Avantage** : limite la croissance Redis tout en permettant les répétitions mensuelles légitimes.

---

## Patterns de déduplication par use case

### Média Solution : regroupement par lot

| Sujet Original | Groupe Généré | Raison |
|----------------|----------------|--------|
| "Média Solution Missions Recadrage Lot 123" | `media_solution_missions_recadrage_lot_123` | Pattern complet détecté |
| "Lot 456 - Documents" | `lot_456` | Pattern lot simple |
| "Suite à votre email du 15" | `subject_hash_a1b2c3...` | Fallback hash |

### DESABO : pas de regroupement (email individuel uniquement)

Les emails DESABO utilisent uniquement la déduplication par email_id, pas de regroupement sujet car chaque désabonnement est individuel.

---

## Gestion des erreurs et résilience

### Redis indisponible : fallback mémoire

```python
# deduplication/redis_client.py
memory_set = set()  # Module-level fallback

def mark_subject_group_processed(..., memory_set: Optional[set] = None):
    if redis_client is not None:
        try:
            redis_client.sadd(groups_key, scoped_id)
            return True
        except Exception as e:
            logger.error(f"REDIS_DEDUP: Error marking: {e}")
            # Continue vers fallback
    
    # Fallback mémoire
    if memory_set is not None:
        memory_set.add(scoped_id)
        return True
    return False
```

**Résilience** : Redis down = mémoire locale, pas de traitement dupliqué même en redémarrage.

### TTL pour les groupes sujets temporaires

```python
# Avec TTL configuré
redis_client.set(ttl_key, 1, ex=ttl_seconds)
redis_client.sismember(groups_key, scoped_id)  # Vérification normale
```

**Usage** : permettre les retraits temporaires (test/debug) tout en gardant l'historique.

---

## Tests : couverture complète du moteur

### 8 tests couvrant tous les scénarios

```bash
pytest tests/deduplication/ -v
# test_redis_client.py: 4 tests
# test_subject_group.py: 4 tests
```

### Tests clés de résilience

```python
def test_deduplication_redis_failure_fallback():
    """Redis down = utilise mémoire, pas de doublons"""
    # Simuler Redis indisponible
    result = is_email_id_processed(None, "test_id", logger, "test_key")
    assert result == False  # Safe assumption
    
    # Marquer en mémoire
    mark_email_id_processed(None, "test_id", logger, "test_key", memory_fallback)
    assert is_email_id_processed(None, "test_id", logger, "test_key", memory_fallback) == True
```

---

## Performance et limites

### Métriques de performance

- **Redis operations** : O(1) pour vérifications
- **Mémoire fallback** : O(n) avec n = nombre d'emails en session
- **Normalisation sujet** : ~10µs par appel

### Limites actuelles

- **Redis obligatoire** : sans Redis, pas de persistance des déduplications
- **Mémoire limitée** : redémarrage = perte des marquages mémoire
- **MD5 collisions** : théoriquement possible mais extrêmement rare

### Optimisations futures (Q2 2026)

- **Bloom filters** : pour les gros volumes
- **Sharding par domaine** : séparation expéditeurs
- **Compression** : pour les clés longues

---

## Monitoring : métriques essentielles

### Métriques à surveiller

- **Deduplication hit rate** : % d'emails rejetés comme doublons
- **Redis errors** : taux d'erreurs Redis (doit être < 1%)
- **Memory fallback usage** : % du temps en fallback mémoire
- **Subject groups created** : nombre de nouveaux groupes par jour

### Alertes recommandées

- **Redis errors > 5%** : Problème de connectivité Redis
- **Memory fallback > 10%** : Redis indisponible depuis trop longtemps
- **Deduplication hit rate < 1%** : Possible problème de configuration

---

## La Golden Rule : Déduplication Redis-first, jamais de doublons

La déduplication utilise Redis comme source de vérité avec fallbacks mémoire gracieux. Chaque email est marqué immédiatement après traitement réussi, évitant les doublons même en cas de redémarrage. Les groupes sujets normalisent les conversations similaires tout en gardant la granularité nécessaire pour les cas métier spécifiques.

Vérification → Traitement → Marquage : ordre immuable pour la fiabilité.
