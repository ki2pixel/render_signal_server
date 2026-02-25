# Troubleshooting

**TL;DR**: Guide de dépannage pour les problèmes courants : Gmail Push, webhooks, SSL, authentification, et monitoring. Chaque problème inclut symptômes, causes probables, diagnostics, et solutions.

---

## La solution : service de diagnostic automobile

Pensez au troubleshooting comme un service de diagnostic automobile : chaque problème a des symptômes clairs (voyants lumineux), des causes probables (pannes mécaniques), des outils de diagnostic (tests), et des solutions documentées (procédures de réparation). Les logs structurés sont les rapports de diagnostic détaillés.

---

## Idées reçues sur le service de diagnostic

### ❌ "Les problèmes sont toujours complexes"
La plupart des problèmes ont des causes simples : token manquant, URL incorrecte, ou configuration mal définie. Le service de diagnostic commence par les vérifications de base avant d'explorer les scénarios complexes.

### ❌ "Il faut être expert pour dépanner"
Les diagnostics sont automatisés : health checks, tests de connectivité, et logs structurés. Le service de diagnostic fournit les outils et les procédures, pas l'expertise.

### ❌ "Le dépannage bloque la production"
Les tests sont non-intrusifs et les diagnostics sont en lecture seule. Le service de diagnostic observe sans perturber, comme un mécanicien qui inspecte sans démonter le véhicule.

---

## Tableau des approches de dépannage

| Approche | Temps de diagnostic | Fiabilité | Complexité | Documentation | Maintenance |
|----------|-------------------|-----------|------------|----------------|------------|
| Intuition | Variable | 40% | Très élevée | Nulle | Élevée |
| Service de diagnostic | 5-15 min | 95%+ | Faible | Complète | Faible |
| Expert externe | 30-60 min | 80%+ | Variable | Partielle | Variable |
| IA assistée | 10-30 min | 70% | Moyenne | Automatisée | Moyenne |

---

## Problèmes Gmail Push Ingress

### Symptôme : `POST /api/ingress/gmail` retourne 401 Unauthorized

**Causes probables** :
- `PROCESS_API_TOKEN` manquant ou incorrect dans les variables Render
- Token Apps Script mal configuré
- En-tête `Authorization: Bearer <token>` absent ou mal formaté

**Diagnostics** :
```bash
# Vérifier la variable d'environnement
echo $PROCESS_API_TOKEN

# Test avec curl
curl -X POST https://your-domain.onrender.com/api/ingress/gmail \
  -H "Authorization: Bearer VOTRE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sender":"test@example.com","body":"test","subject":"test"}'
```

**Solutions** :
1. Configurer `PROCESS_API_TOKEN` dans les variables Render
2. Mettre à jour le token dans Google Apps Script
3. Vérifier le format de l'en-tête `Authorization: Bearer <token>`

---

### Symptôme : `POST /api/ingress/gmail` retourne 400 Invalid JSON payload

**Causes probables** :
- Payload JSON invalide ou mal formé
- Champs obligatoires manquants (`sender`, `body`)
- Erreur de syntaxe dans le JSON Apps Script

**Diagnostics** :
```bash
# Vérifier le payload Apps Script
# Dans Apps Script Logger
Logger.log("Payload: " + JSON.stringify(payload))

# Test avec payload valide
curl -X POST https://your-domain.onrender.com/api/ingress/gmail \
  -H "Authorization: Bearer $PROCESS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sender":"test@example.com","body":"test","subject":"test"}'
```

**Solutions** :
1. Valider le JSON avant envoi depuis Apps Script
2. S'assurer que `sender` et `body` sont présents
3. Corriger la syntaxe JSON (guillemets, quotes)

---

### Symptôme : Aucun webhook envoyé

**Causes probables** :
- `WEBHOOK_URL` non défini ou joignable
- Erreurs réseau côté serveur cible
- Modifications UI non persistées (fichier lock)
- Store externe PHP inaccessible

**Diagnostics** :
```bash
# Vérifier la configuration webhook
curl -s https://your-domain.onrender.com/api/webhooks/config | jq '.webhook_url'

# Vérifier les logs d'écriture
grep "SVC.*WebhookConfigService.*update_config" render.log

# Tester la connectivité
curl -I -X POST $WEBHOOK_URL -H "Content-Type: application/json" \
  -d '{"test": "connection"}'
```

**Solutions** :
1. Configurer `WEBHOOK_URL` dans les variables Render
2. Vérifier les permissions des fichiers `debug/webhook_config.json`
3. Tester la connectivité réseau vers le webhook cible
4. Si API PHP utilisée, vérifier `EXTERNAL_CONFIG_BASE_URL` et `CONFIG_API_TOKEN`

---

## Problèmes SSL et Webhooks

### Symptôme : `SSLError: certificate verify failed`

**Causes probables** :
- Le certificat ne couvre pas le FQDN utilisé dans `WEBHOOK_URL`
- Mauvaise configuration SNI/vhost côté reverse proxy
- Certificat expiré ou invalide

**Diagnostics** :
```bash
# Vérifier le certificat
openssl s_client -connect $WEBHOOK_URL:443 -servername $(echo $WEBHOOK_URL | cut -d'/' | cut -d':' -f1) \
  -showcerts </dev/null | openssl x509 -noout -subject -issuer -dates -ext subjectAltName

# Test de connexion HTTPS
curl -svI $WEBHOOK_URL --max-time 10
```

**Solutions** :
1. **Recommandé** : Émettre un certificat incluant le hostname exact
2. **Alternative** : Modifier `WEBHOOK_URL` pour cibler un hostname couvert
3. **Temporaire** : `WEBHOOK_SSL_VERIFY=false` (non recommandé en production)
4. **Maintenance** : Surveiller l'expiration et renouvellement

---

## Problèmes d'Authentification

### Symptôme : Interface affiche "Authentification requise"

**Causes probables** :
- Session Flask expirée
- Magic link invalide ou expiré
- `TRIGGER_PAGE_PASSWORD` incorrect

**Diagnostics** :
```bash
# Vérifier la session
curl -s https://your-domain.onrender.com/api/ping | jq '.authenticated'

# Vérifier les logs de connexion
grep "LOGIN.*success\|LOGIN.*failed" render.log

# Vérifier les magic links
grep "MAGIC_LINK.*token" render.log
```

**Solutions** :
1. Reconnexion via `/login`
2. Générer un nouveau magic link depuis `/login`
3. Vérifier `TRIGGER_PAGE_PASSWORD` dans les variables Render
4. Si magic link, vérifier `FLASK_SECRET_KEY` cohérent

---

## Problèmes de Performance

### Symptôme : Application lente ou timeouts fréquents

**Causes probables** :
- Conteneur Render Free suspendu
- Mémoire insuffisante
- Timeout IMAP trop court
- Trop de requêtes simultanées

**Diagnostics** :
```bash
# Vérifier l'état du conteneur
curl -s https://your-domain.onrender.com/health | jq '.status'

# Vérifier l'utilisation mémoire
curl -s https://your-domain.onrender.com/api/metrics | jq '.memory_usage_mb'

# Vérifier les timeouts IMAP
grep "IMAP.*timeout" render.log
```

**Solutions** :
1. Configurer un monitoring externe (UptimeRobot ≤5min)
2. Augmenter `IMAP_TIMEOUT_SECONDS` si nécessaire
3. Optimiser les requêtes (cache, pagination)
4. Surveiller les métriques de performance

---

## Problèmes Multi-conteneurs

### Symptôme : Double traitement des emails

**Causes probables** :
- Verrou distribué Redis non configuré (IMAP legacy)
- Plusieurs conteneurs avec `ENABLE_BACKGROUND_TASKS=true` (IMAP legacy)
- Fallback file lock utilisé en multi-conteneurs (IMAP legacy)
- Gmail Apps Script retry (double POST identique)

**Diagnostics** :
```bash
# Vérifier le verrou Redis (IMAP legacy)
redis-cli GET render_signal:poller_lock

# Vérifier les logs de polling (IMAP legacy)
grep "BG_POLLER.*lock" render.log

# Vérifier la configuration Redis
echo $REDIS_URL

# Vérifier les logs Gmail Push idempotence
grep "already_processing" render.log
```

**Solutions** :
1. **Solution moderne (Gmail Push)** : Le verrou "in-flight" est automatique
   - Aucune configuration requise
   - Status `already_processing` normal pour double POST
   - Documentation : [docs/ingestion/gmail-push.md](../ingestion/gmail-push.md#3-idempotence-verrou-in-flight-pour-double-post)

2. **Solution legacy (IMAP)** : Configurer `REDIS_URL` pour le verrou distribué
   - `REDIS_URL=redis://user:pass@host:port/db`
   - Redémarrer les conteneurs
   - Vérifier les logs de lock acquisition

---

## Problèmes R2 Offload

### Symptôme : Fichiers non offloadés vers R2

**Causes probables** :
- `R2_FETCH_TOKEN` manquant ou incorrect
- Worker Cloudflare indisponible
- Timeout R2 trop court
- Domaine non autorisé dans le Worker

**Diagnostics** :
```bash
# Vérifier la configuration R2
echo $R2_FETCH_ENABLED
echo $R2_FETCH_ENDPOINT
echo $R2_FETCH_TOKEN

# Tester le Worker directement
curl -X POST $R2_FETCH_ENDPOINT \
  -H "X-R2-FETCH-TOKEN: $R2_FETCH_TOKEN" \
  -d '{"source_url":"https://dropbox.com/test"}'

# Vérifier les logs R2
grep "R2_TRANSFER" render.log
```

**Solutions** :
1. Configurer `R2_FETCH_TOKEN` identique entre Render et Worker
2. Vérifier la connectivité au Worker Cloudflare
3. Augmenter les timeouts pour les dossiers Dropbox `/scl/fo/`
4. Vérifier la allowlist de domaines dans le Worker

---

## Tests de Diagnostic

### Tests de connectivité

```bash
# Health check complet
curl -s https://your-domain.onrender.com/health | jq '.'

# Test Gmail Push
curl -X POST https://your-domain.onrender.com/api/ingress/gmail \
  -H "Authorization: Bearer $PROCESS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sender":"test@example.com","body":"test","subject":"test"}'

# Test webhook cible
curl -I -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"test":"connection"}'
```

### Tests de performance

```bash
# Test de charge simple
for i in {1..10}; do
  curl -s https://your-domain.onrender.com/api/health &
  sleep 0.1
done

# Test de mémoire
curl -s https://your-domain.onrender.com/api/metrics | jq '.memory_usage_mb'
```

### Tests de résilience

```bash
# Test Redis
redis-cli ping

# Test fallback R2
curl -X POST $R2_FETCH_ENDPOINT \
  -H "X-R2-FETCH-TOKEN: $R2_FETCH_TOKEN" \
  -d '{"source_url":"https://dropbox.com/test"}' \
  --max-time 15
```

---

## Logs Importants à Surveiller

### Logs critiques à surveiller

```bash
# Erreurs critiques
grep -E "(ERROR|CRITICAL|FATAL)" render.log

# Taux d'erreur élevé
grep "error_rate.*>" render.log

# Timeouts et reconnexions
grep -E "(timeout|reconnect|failed)" render.log

# Fallbacks R2
grep "R2_TRANSFER.*fallback" render.log

# Verrou distribué
grep "BG_POLLER.*lock" render.log
```

### Logs de performance

```bash
# Temps de traitement
grep "duration_ms" render.log | tail -10

# Utilisation mémoire
grep "memory_usage" render.log | tail -10

# Événements système
grep "PROCESS:" render.log | tail -10
```

---

## Commandes de Diagnostic

### Commandes essentielles

```bash
# État général du système
curl -s https://your-domain.onrender.com/health

# Métriques de performance
curl -s https://your-domain.onrender.com/api/metrics

# Logs récents
tail -n 50 render.log | grep -E "(ERROR|WARNING|CRITICAL)"

# État Redis
redis-cli info
redis-cli GET render_signal:poller_lock
```

### Scripts de diagnostic

```bash
# Diagnostic complet
curl -s https://your-domain.onrender.com/health | jq '.services'

# Test complet Gmail Push
curl -X POST https://your-domain.onrender.com/api/ingress/gmail \
  -H "Authorization: Bearer $PROCESS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sender":"test@example.com","body":"test","subject":"test"}'

# Simulation de webhook
python debug/simulate_webhooks.py --scenario dropbox
```

---

## La Golden Rule : Diagnostics Structurés + Tests Cibles + Solutions Documentées

Chaque problème inclut des symptômes clairs, des diagnostics précis, et des solutions éprouvées. Les tests de validation permettent de confirmer la résolution. Les logs structurés et les health checks assure une visibilité complète sur la santé du système.

---

*Pour la configuration complète : voir `docs/v2/core/configuration-reference.md`. Pour le déploiement : voir `docs/v2/ops/deployment.md`.*
