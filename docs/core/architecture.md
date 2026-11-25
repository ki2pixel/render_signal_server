# Architecture Orientée Services

**TL;DR**: On a remplacé un monolithe Flask par des services singletons avec Redis comme source de vérité. Le polling IMAP est mort, Gmail Push règne.

---

## Le problème : le monolithe qui ne tenait plus

J'ai hérité d'un fichier `app_render.py` de 1500 lignes. Tout était mélangé : configuration, authentification, polling IMAP, envoi de webhooks. Pire encore, le polling IMAP consommait toute la bande passante de Render et les configurations étaient éparpillées dans des globals modifiés au runtime.

Les déploiements multi-conteneurs ? Impossible. Chaque instance avait sa propre copie des configurations, et quand deux pollers IMAP démarraient en même temps, ils se battaient pour les mêmes emails.

---

## La solution : orchestre avec section centrale Redis

Pensez à l'architecture comme un orchestre : chaque service est un musicien spécialisé (violons, cuivres, percussions) dirigé par un chef d'orchestre (Redis) qui assure la cohérence. Le polling IMAP était un musicien solo désynchronisé; Gmail Push est le chef qui donne le tempo.

### ❌ L'ancien monde : musiciens solo sans chef

```python
# Dans app_render.py - ANTI-PATTERN
global webhook_config
webhook_config = load_webhook_config()  # Une seule fois au démarrage

# Plus tard, dans une route
webhook_config['url'] = new_url  # Mutation globale
save_webhook_config(webhook_config)
```

### ✅ Le nouveau monde : orchestre synchronisé

```python
# services/webhook_config_service.py
class WebhookConfigService:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 30  # secondes
    
    def get_config(self):
        if self._is_cache_expired():
            self._cache = self._app_config_store.get_config_json("webhook_config")
        return self._cache
    
    def update_config(self, config):
        self._app_config_store.set_config_json("webhook_config", config)
        self._invalidate_cache()
```

---

## Idées reçues sur l'orchestre

### ❌ "Les singletons sont un anti-pattern"
Les singletons ici sont contrôlés (get_instance()) et servent de cache court (30-60s). Ce ne sont pas des globals modifiés, mais des musiciens qui gardent leur partition en mémoire pour ne pas la relire à chaque note.

### ❌ "Redis est une dépendance critique"
Redis a un fallback fichier garanti. Si Redis tombe, l'orchestre continue en mode dégradé avec les partitions locales. C'est comme un chef d'orchestre qui utilise sa mémoire si la partition papier est perdue.

### ❌ "Gmail Push est compliqué à mettre en place"
Gmail Apps Script fait tout le travail : webhook, authentification, formatage. C'est 50 lignes de JavaScript vs 500 lignes de polling IMAP. Le chef d'orchestre délègue le tempo au métronome électronique.

---

## Tableau des approches d'architecture

| Approche | Complexité | Multi-conteneurs | Performance | Maintenance | Résilience |
|----------|------------|------------------|--------------|----------------|------------|
| Monolithe globals | Très faible | Impossible | Moyenne | Très faible | Nulle |
| Services + fichiers | Moyenne | Difficile | Bonne | Moyenne | Faible |
| Services + Redis | Moyenne | Excellente | Optimisée | Élevée | Élevée |
| Microservices | Élevée | Excellente | Variable | Variable | Très élevée |

---

## Architecture : l'orchestre par sections

### Section principale (singletons)

| Service | Rôle dans l'orchestre | Pourquoi un singleton ? |
|---------|-------------------|------------------------|
| `RuntimeFlagsService` | Chef d'orchestre (tempo, directions) | Partagé par toute l'application, cache 60s |
| `WebhookConfigService` | Section cuivres (messages sortants) | Évite les relectures disque, centralise la validation |
| `RoutingRulesService` | Section cordes (routage complexe) | Cache TTL 30s, Redis-first |
| `IngressService` | Salle d'arrivée (Gmail Push) | Un seul point d'entrée, exécuteur borné et déduplication partagée |
| `DeduplicationService` | Mémoire collective (Redis + fallback) | Verrou in-flight partagé entre workers |
| `MagicLinkService` | Porte d'entrée (billets) | Partage entre instances, stockage JSON verrouillé |
| `R2TransferService` | Section percussions (transferts lourds) | Connexions réutilisées, normalisation Dropbox |
| `RateLimitService` | Métronome (débit sortant) | Compteur partagé entre workers |
| `RuntimeMetricsService` | Tableau de bord (mesures) | Agrégats cohérents entre requêtes |
| `WebhookLoggerService` | Enregistreur de vol | Journal centralisé Redis + fichier |

### Musiciens autonomes (stateless)

| Service | Rôle | Injection |
|---------|------|-----------|
| `ConfigService` | Variables ENV + accordeur | Injecté dans `app_render.py` |
| `AuthService` | Contrôle d'accès salle | Initialisé au démarrage |

---

## Chef d'orchestre Redis : source de vérité centralisée

### Le problème des partitions volatiles

Le filesystem de Render est éphémère. À chaque redéploiement, les partitions disparaissaient. Pire : en multi-conteneur, chaque musicien avait sa propre version de la partition.

### La solution : chef d'orchestre Redis

```python
# config/app_config_store.py
class AppConfigStore:
    def get_config_json(self, key):
        # 1. Essayer Redis d'abord
        if self._redis_client:
            try:
                data = self._redis_client.get(f"r:ss:{key}:v1")
                if data:
                    return json.loads(data)
            except RedisError:
                logger.warning(f"Redis failed for {key}, falling back to file")
        
        # 2. Fallback fichier local
        return self._load_from_file(key)
    
    def set_config_json(self, key, data):
        # Écriture atomique : Redis + fichier
        if self._redis_client:
            self._redis_client.setex(f"r:ss:{key}:v1", 3600, json.dumps(data))
        self._save_to_file(key, data)
```

**Résultat** : les partitions survivent aux redeploys et sont partagées entre tous les musiciens de l'orchestre.

---

## Gmail Push : le chef qui donne le tempo

### ❌ Musicien solo IMAP : le chaos rythmique

- Bande passante consommée 24/7
- Connexions qui timeout toutes les 5 minutes
- Locks distribués complexes pour éviter les doublons
- Logs de retry partout

### ✅ Chef d'orchestre Gmail Push : la précision rythmique

```python
# routes/api_ingress.py
@bp.route("/gmail", methods=["POST"])
def ingest_gmail() -> tuple[Response, int] | Response:
    if not _auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Invalid JSON payload"}), 400

    ar = sys.modules.get("app_render")
    if ar is None:
        return jsonify({"success": False, "message": "Server not ready"}), 503

    ingress_service = getattr(ar, "_ingress_service", None)
    if not ingress_service:
        return jsonify({"success": False, "message": "Service unavailable"}), 503

    result, status_code = ingress_service.process_gmail_push(payload)
    return jsonify(result), status_code
```

**Le gain** : la route est désormais un contrôleur extrêmement mince. Toute la complexité d'ingestion (validation, déduplication, fenêtres horaires et offload R2) est déléguée à la classe singleton `IngressService` (dans `services/ingress_service.py`), respectant le principe de responsabilité unique.

### Résolution des créneaux hors fenêtre

`email_processing/delivery_time_resolver.py` centralise le report des missions « Média Solution – Missions Recadrage » dont l'heure cible tombe hors de la fenêtre globale. La cible brute reste produite par `check_media_solution_pattern` ; la résolution intervient au moment de construire le payload.

| Fonction | Contrat |
| --- | --- |
| `parse_received_datetime(raw, tz, fallback)` | Convertit une date ISO 8601 ou RFC 2822 dans le fuseau de polling |
| `is_urgent_subject(subject)` | Détecte `URGENCE` avec la même règle que le pattern matching |
| `resolve_recadrage_delivery_time(value, *, received_dt, window_start, window_end, target_morning_time="09h00", is_urgent=False)` | Reporte la cible au prochain matin ouvré ; retourne la chaîne d'origine si la fenêtre est absente/invalide, si le format est inconnu ou si le sujet est urgent |

Les deux chemins d'ingestion partagent ce module : `IngressService._resolve_recadrage_delivery_time` (Gmail Push) et `orchestrator._resolve_out_of_window_delivery_time` (IMAP legacy). Le samedi est ouvré, le dimanche est exclu, les jours fériés ne sont pas gérés.

---

## Frontend modulaire : du soliste JavaScript à l'orchestre ES6

### ❌ L'ancien dashboard.js : soliste surchargé

Tout était mélangé : appels API, gestion DOM, logs, états UI. Ajouter une fonctionnalité ? Risque de tout casser.

### ✅ La nouvelle orchestre modulaire

```
static/
├── services/
│   ├── ApiService.js           # Client HTTP centralisé
│   ├── WebhookService.js       # Config + logs webhooks
│   ├── LogService.js           # Timer intelligent + timeline
│   ├── RoutingRulesService.js  # Builder de règles + rendu Redis
│   ├── autosave.js             # Auto-save debounced + rollback
│   ├── config_io.js            # Import/export et flags runtime
│   ├── deploy.js               # Déploiement Render
│   ├── magic_link.js           # Génération/copie des magic links
│   ├── panels.js               # État replié/déplié des panneaux
│   └── status_banner.js        # Bandeau de statut accessible
├── components/
│   ├── TabManager.js           # Onglets accessibles (ARIA, deep-linking)
│   ├── ConfirmDialog.js        # Modale de confirmation (role=alertdialog)
│   └── JsonViewer.js           # Visualiseur JSON
├── utils/
│   ├── MessageHelper.js        # Messages, toasts, erreurs
│   ├── DOMHelper.js            # Construction DOM sécurisée
│   ├── debounce.js             # Debounce partagé
│   └── listenerRegistry.js     # Cycle de vie des listeners
└── dashboard.js                # Orchestrateur (237 lignes)
```

**Impact** : `dashboard.js` est passé de 1488 à 237 lignes ; chaque module porte une responsabilité unique et l'accessibilité (onglets, confirmation, toasts) est centralisée.

---

## Patterns récurrents : les partitions de l'orchestre

### 1. Singletons avec mémoire partition

Tous les services critiques sont des singletons avec une mémoire à court terme (30-60s). ça évite de relire les partitions tout en garantissant la fraîcheur de l'interprétation.

```python
# Pattern singleton
class RoutingRulesService:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

### 2. Validation à l'entrée de salle

Aucune validation n'est faite au cœur de l'orchestre. Tout se passe à l'entrée (routes Flask) :

```python
# routes/api_routing_rules.py
@bp.route("/api/routing_rules", methods=["POST"])
@login_required
def update_routing_rules():
    payload = RoutingRulesSchema().load(request.json)
    routing_service.update_rules(payload)
    return jsonify({"status": "ok"})
```

### 3. Continuité gracieuse

Chaque musicien qui parle à l'extérieur (Redis, R2, APIs) a une continuité :

```python
# services/r2_transfer_service.py
def upload_to_r2(self, source_url):
    try:
        return self._worker_client.fetch(source_url)
    except (WorkerTimeout, WorkerError):
        logger.warning(f"R2 offload failed for {source_url}, keeping original")
        return {"r2_url": None, "original_url": source_url}  # Fallback
```

---

## Complexité surveillée : les solos à garder sous contrôle

| Musicien | Complexité radon | Statut | Plan d'action | Documentation |
|-----------|------------------|--------|---------------|---------------|
| `orchestrator.py::check_new_emails_and_trigger_webhook` | F (43) | ❌ Legacy | Isoler les branches Media Solution/DESABO | [docs/ingestion/legacy-imap.md](../ingestion/legacy-imap.md) |
| `routes/api_webhooks.py::_parse_and_validate_webhook_payload` | E (36) | ✅ Actif | Extraire les validateurs par champ | [docs/processing/webhooks-outbound.md](../processing/webhooks-outbound.md) |
| `email_processing/pattern_matching.py::check_media_solution_pattern` | E (33) | ✅ Actif | Séparer urgence / date-heure / heure seule | [docs/processing/pattern-matching.md](../processing/pattern-matching.md) |
| `preferences/processing_prefs.py::validate_processing_prefs` | E (32) | ✅ Actif | Simplifier la validation par schéma | [docs/processing/routing-engine.md](../processing/routing-engine.md) |
| `services/r2_transfer_service.py::normalize_source_url` | E (31) | ✅ Actif | Stratégie par fournisseur | [docs/processing/file-offload.md](../processing/file-offload.md) |
| `services/ingress_service.py::IngressService._process_single_delivery_link` | D (21) | ✅ Actif | Isoler le fetch R2 et son fallback | [docs/ingestion/gmail-push.md](../ingestion/gmail-push.md) |
| `services/webhook_config_service.py::WebhookConfigService.update_config` | D (21) | ✅ Actif | Nettoyer la logique de cache | [docs/processing/webhooks-outbound.md](../processing/webhooks-outbound.md) |
| `services/ingress_service.py::IngressService.process_gmail_push` | B (8) | ✅ Actif | Résolu : délégué aux helpers et singletons | [docs/ingestion/gmail-push.md](../ingestion/gmail-push.md) |
| `email_processing/orchestrator.py::send_custom_webhook_flow` | B (7) | ✅ Actif | Résolu : routage et enrichissement isolés | [docs/processing/webhooks-outbound.md](../processing/webhooks-outbound.md) |
| `services/magic_link_service.py::MagicLinkService.consume_token` | A (5) | ✅ Actif | Résolu : validation HMAC simplifiée | [docs/core/magic-link-auth.md](magic-link-auth.md) |

**Moyenne actuelle** : C (16.85) sur 59 blocs analysés (`radon cc` hors tests).

**La règle** : aucun solo ne doit dépasser 40 lignes logiques. Si c'est le cas, on extrait.

### ❌ Pourquoi ces hotspots sont critiques

Les fonctions F/E concentrent la logique métier et les points de défaillance :

- **`check_new_emails_and_trigger_webhook (F)`** : boucle IMAP legacy qui porte encore pattern matching, routing et envoi. Une erreur ici bloque le poller de secours.
- **`_parse_and_validate_webhook_payload (E)`** : validation monolithique de la configuration webhook (URL, SSL, fenêtres, absence).
- **`check_media_solution_pattern (E)`** : extraction urgence/date/heure dans une seule fonction, difficile à couvrir exhaustivement.
- **`validate_processing_prefs (E)`** : validation qui mélange schéma et règles métier.

### ✅ Stratégie de refactoring en cours

1. **Extraction des helpers** : `process_gmail_push` (B) a été scindée en méthodes privées (`_validate_payload()`, `_evaluate_time_window_policy()`, `_resolve_recadrage_delivery_time()`, `_maybe_enrich_delivery_links_with_r2()`).
2. **Isolation des responsabilités** : `send_custom_webhook_flow` (B) délègue le routage et l'enrichissement ; les validateurs webhook restent à extraire.
3. **Validation par schéma** : remplacer `validate_processing_prefs` par une validation déclarative.

---

## Déploiement : Docker + GHCR + Render

### Le pipeline en 3 étapes

1. **Build GitHub Actions** : `docker build` → push sur GHCR avec tags `latest` et `<sha>`
2. **Déclenchement Render** : Deploy Hook prioritaire, puis API Render, fallback manuel
3. **Runtime** : Gunicorn derrière reverse proxy, variables d'env injectées

```dockerfile
# Dockerfile - multi-stage pour optimisation
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim as runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app_render:app"]
```

---

## Monitoring : les logs qui comptent vraiment

### Logs critiques à surveiller

```
CFG WEBHOOK: Custom webhook URL configured          # Startup OK
INGRESS: gmail payload received (email_id=..., sender=..., subject=...)  # Ingestion OK  
PROCESS: SIGTERM received                         # Arrêt propre
R2_TRANSFER: Successfully transferred <provider> link to R2  # Offload OK
```

### Alertes recommandées

- **Aucun `INGRESS: gmail payload received`** depuis 15 minutes → Gmail Apps Script down
- **`WARNING` ou `ERROR`** répétés → problème de configuration
- **`R2_TRANSFER: failed`** > 5/heure → Worker R2 down

---

## Le futur : ce qui reste à simplifier

1. **Orchestrator** : extraire les branches Media Solution/DESABO dans des services dédiés
2. **Pattern matching** : créer un moteur de détection externe (regex + heuristiques)  
3. **Preferences** : migration vers Pydantic pour la validation
4. **Tests** : passer de 67% à 80% de couverture sur les modules critiques

---

## La Golden Rule : Orchestre synchronisé, partitions centralisées

Les services sont des musiciens singletons avec mémoire courte. Les partitions vivent dans Redis avec fallback fichier. Le tempo est donné par Gmail Push. Tout le reste découle de ces trois principes orchestraux.
