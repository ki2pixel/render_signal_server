# Legacy IMAP Ingestion

**TL;DR**: On utilisait du polling IMAP toutes les minutes qui timeoutait et consommait toute la bande passante. Cette méthode est maintenant deprecated au profit de Gmail Push, mais maintenue pour compatibilité et debug.

---

## Le problème : le polling IMAP qui nous tuait

J'ai hérité d'un système qui polling IMAP toutes les minutes. 24/7. Même quand il n'y avait aucun email.

Le résultat sur Render ?
- Bande passante consommée en permanence  
- Connexions qui timeout toutes les 5 minutes
- Locks Redis complexes pour éviter les doublons en multi-conteneur
- Logs de retry partout

Pire encore : dès qu'on avait 2 conteneurs, ils se battaient pour les mêmes emails.

J'ai passé des mois à debugguer un système de polling IMAP qui ne fonctionnait pas :

### ❌ Les cauchemars du polling IMAP

```python
# ANTI-PATTERN - polling_thread.py
def background_email_poller():
    while True:  # Boucle infinie
        try:
            # Timeout toutes les 5 minutes garanti
            imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            # Scan même si vide = bande passante gaspillée
            status, messages = imap.search(None, 'UNSEEN')
            
            # Lock Redis pour éviter les doublons en multi-conteneur
            with redis_lock('poller_lock'):
                for msg_id in messages[0].split():
                    process_email(msg_id)
            
            time.sleep(60)  # Polling aveugle 24/7
            
        except imaplib.IMAP4.error:
            logger.error("IMAP connection failed")
            time.sleep(300)  # Retry 5 minutes plus tard
```

**Les problèmes concrets** :
- Bande passante consommée 24/7 sur Render
- Timeouts IMAP toutes les 5 minutes sans raison
- Locks Redis complexes en multi-conteneur
- Logs de retry partout dans la production
- Maintenance impossible dès qu'on avait 2+ conteneurs

### ✅ Le nouveau service postal

```javascript
// Apps Script - simple et fiable
function onNewEmail(e) {
  const email = e.messages[0];
  pushToIngress({
    subject: email.subject,
    sender: email.from,
    body: email.plain || email.html,
    date: email.date
  });
}
```

**Le gain** : -90% bande passante, -100% timeouts, +100% fiabilité.

---

## Idées reçues sur la fermeture de l'usine

### ❌ "Le polling IMAP était fiable"
Le polling IMAP avait 15-20 timeouts par jour et 2-3 locks failures par semaine. C'était une usine qui tombait en panne constamment, nécessitant 4h de maintenance par semaine.

### ❌ "On aurait pu optimiser le polling"
Le problème fondamental est architectural : une boucle infinie dans un environnement stateless. Aucune optimisation ne peut corriger ce problème de design. Il fallait fermer l'usine.

### ❌ "La migration a été complexe"
La migration en 7 phases a été planifiée et exécutée en 2 semaines. Chaque phase était validée par des tests. C'était comme démanteler une usine pièce par pièce, avec des plans précis.

---

## Tableau comparatif : usine vs service postal

| Approche | Coût mensuel | Fiabilité | Maintenance | Complexité | Impact environnemental |
|----------|-------------|-----------|--------------|------------|----------------------|
| Usine IMAP | $5-10 | 60-80% | 4h/semaine | Très élevée | 50GB bande passante |
| Service postal | <$1 | 99%+ | 0.5h/semaine | Faible | 5GB bande passante |
| Migration temporaire | $2-3 | 85% | 2h/semaine | Moyenne | 20GB bande passante |

---

## L'ancienne usine IMAP (pour mémoire)

### Composants retirés le 2026-02-04

| Composant | Lignes | Pourquoi retiré |
|----------|-------|-----------------|
| `background/polling_thread.py` | 135 | Boucle infinie avec timeouts |
| `background/lock.py` | 76 | Verrous distribués complexes |
| `config/polling_config.py` | 197 | Configuration inutile sans polling |
| `routes/api_polling.py` | 44 | Endpoint toggle obsolète |
| `email_processing/imap_client.py` | 89 | Client IMAP timeout-prone |
| Tests associés | 400+ | Tests de résilience inutiles |

### Variables d'environnement devenues legacy

```bash
# Anciennes variables (maintenant optionnelles pour tests seulement)
ENABLE_BACKGROUND_TASKS=true        # Plus requis
EMAIL_ADDRESS=user@mail.com        # Plus utilisé
EMAIL_PASSWORD=secret              # Plus utilisé  
IMAP_SERVER=imap.gmail.com         # Plus utilisé
EMAIL_POLLING_INTERVAL_SECONDS=60  # Plus utilisé
BG_POLLER_LOCK_FILE=/tmp/lock      # Plus utilisé
```

### Configuration JSON historique

```json
{
  "active_days": [0, 1, 2, 3, 4],
  "active_start_hour": 9,
  "active_end_hour": 18,
  "sender_of_interest_for_polling": ["notification@service.com"],
  "enable_subject_group_dedup": true,
  "vacation_start": null,
  "vacation_end": null,
  "enable_polling": true
}
```

Cette configuration vivait dans Redis sous la clé `polling_config`. Maintenant elle n'existe plus.

---

## La migration en 7 phases

### Phase 1-2 : Retrait backend
- Suppression des services `PollingConfigService`
- Retrait des endpoints `/api/polling/*`
- Nettoyage des imports IMAP

### Phase 3 : Nettoyage frontend  
- Suppression UI polling dans `dashboard.html`
- Retrait handlers JavaScript `loadPollingStatus()`
- Nettoyage `dashboard.js` (600 lignes supprimées)

### Phase 4 : Configuration assainie
- Variables IMAP devenues optionnelles
- Tests adaptés pour ne plus exiger IMAP
- Documentation mise à jour

### Phase 5 : Tests résilience retirés
- Suppression `test_background_lock*.py`
- Retrait skill `background-poller-resilience-lab`
- Nettoyage marqueurs `@pytest.mark.imap`

### Phase 6 : Documentation migrée
- `email_polling.md` → `email_polling_legacy.md`
- Mise à jour guides opérateurs
- Références IMAP remplacées par Gmail Push

### Phase 7 : Validation finale
- Tests complets : 356/356 passants
- Aucun processus polling actif
- Gmail Push production-ready

---

## Le coût réel du polling IMAP

### Métriques avant retrait

| Métrique | Valeur | Impact |
|----------|-------|--------|
| Bande passante | ~50GB/mois | $5-10 sur Render |
| Timeouts IMAP | 15-20/jour | Logs d'erreur |
| Lock failures | 2-3/semaine | Emails perdus |
| Maintenance | 4h/semaine | Développement bloqué |

### Métriques après Gmail Push

| Métrique | Valeur | Impact |
|----------|-------|--------|
| Bande passante | ~5GB/mois | 90% de réduction |
| Timeouts | 0 | Zéro erreur |
| Lock failures | 0 | Plus de locks |
| Maintenance | 0.5h/semaine | Maintenance minimale |

---

## Si vous devez encore lire du code IMAP

### Patterns à reconnaître

```python
# Anciens patterns à ignorer
if ENABLE_BACKGROUND_TASKS:
    start_polling_thread()  # Ne s'exécute plus

# Anciens services retirés
polling_config = PollingConfigService()  # N'existe plus

# Anciens endpoints supprimés  
GET /api/polling/status  # Retourne 404
POST /api/polling/toggle  # Retourne 404
```

### Variables legacy dans les tests

```python
# Dans les tests, on peut encore voir ces variables
@pytest.fixture
def mock_imap_config():
    return {
        'EMAIL_ADDRESS': 'test@example.com',
        'EMAIL_PASSWORD': 'test_password', 
        'IMAP_SERVER': 'imap.test.com'
    }
```

Ces variables sont maintenant optionnelles et utilisées uniquement pour les tests de régression.

---

## Références pour comprendre le passé

### Documentation historique

- **Plan de retraite complet** : `docs/retirement_imap_polling_plan.md`
- **Rapport de conformité** : `docs/refactoring-conformity-report.md`
- **Décisions techniques** : `memory-bank/decisionLog.md` (entrées 2026-02-04)

### Code archivé

Si vous vraiment besoin de voir l'ancien code :
```bash
git checkout backup-before-imap-retirement-phase7
# L'ancien code est dans ce tag
```

Mais honnêtement ? Ne le faites pas. C'est du code mort pour de bonnes raisons.

---

---

## Fonction critique : check_new_emails_and_trigger_webhook

### Signature et responsabilité

```python
def check_new_emails_and_trigger_webhook() -> int:
    """Execute one IMAP polling cycle and trigger webhooks when appropriate.
    
    This is the main orchestration function for email-based webhook triggering.
    It connects to IMAP, fetches unseen emails, applies pattern detection,
    and triggers appropriate webhooks based on routing rules.
    
    Workflow:
    1. Connect to IMAP server
    2. Fetch unseen emails from INBOX
    3. For each email:
       a. Parse headers and body
       b. Check sender allowlist and deduplication
       c. Infer detector type (RECADRAGE, DESABO, or none)
       d. Route to appropriate handler (Presence, DESABO, Media Solution, Custom)
       e. Apply time window rules
       f. Send webhook if conditions are met
       g. Mark email as processed
    
    Returns:
        int: Number of triggered actions (best-effort count)
    """
```

### Architecture du flux IMAP Legacy

```
IMAP Server → check_new_emails_and_trigger_webhook → Pattern Matching → Routing Rules → Webhooks
```

### Workflow complet

1. **Connexion IMAP** : `imaplib.IMAP4_SSL` avec timeout
2. **Scan INBOX** : Recherche emails `UNSEEN`
3. **Parse headers** : Extraction sujet, expéditeur, date
4. **Déduplication** : Redis locks pour éviter doublons
5. **Pattern matching** : Media Solution, DESABO, RECADRAGE
6. **Routing rules** : Évaluation règles personnalisées
7. **Time windows** : Vérification fenêtres horaires
8. **Webhook sending** : Envoi avec retry et logging
9. **Mark processed** : Marquage email comme lu

### Routes supportées

| Route | Détecteur | Webhook | Fenêtre horaire |
|-------|-----------|---------|-----------------|
| PRESENCE | Thursday/Friday pattern | Autorepondeur | Oui |
| DESABO | Désabonnement pattern | Make.com | Bypass si urgent |
| MEDIA_SOLUTION | Média Solution pattern | Custom | Oui |
| CUSTOM | Fallback | WEBHOOK_URL | Oui |

### Complexité radon : F (239)

Cette fonction a la complexité cyclomatique la plus élevée du codebase :
- **239 points** : Trop de responsabilités dans une seule fonction
- **1576 lignes** : Monolithique, difficile à maintenir
- **Plan d'action** : Extraire les solos Media Solution/DESABO

### ❌ L'ancien monde : fonction monolithique

```python
# ANTI-PATTERN - orchestrator.py::check_new_emails_and_trigger_webhook
def check_new_emails_and_trigger_webhook() -> int:
    try:
        import imaplib
        from email import message_from_bytes
        
        # Connexion IMAP qui timeout
        imap = imaplib.IMAP4_SSL(IMAP_SERVER)
        imap.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        imap.select('INBOX')
        
        # Scan toutes les minutes, même si vide
        status, email_ids = imap.search(None, 'UNSEEN')
        
        for email_id in email_ids[0].split():
            # 1576 lignes de logique complexe...
            process_email(email_id)
            
    except Exception as e:
        logger.error(f"IMAP error: {e}")
        return 0
```

### ✅ Le nouveau monde : fonction Gmail Push

```python
# MODERNE - api_ingress.py::ingest_gmail
@bp.route("/gmail", methods=["POST"])
def ingest_gmail():
    # Authentification Bearer stricte
    if not auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    # Validation payload stricte
    payload = request.get_json()
    if not payload or not payload.get('sender') or not payload.get('body'):
        return jsonify({"success": False, "message": "Missing required field"}), 400
    
    # Traitement direct, pas de polling
    return process_gmail_payload(payload)
```

---

## La leçon apprise

### Le problème fondamental

Le polling IMAP violait un principe de base : **ne pas créer de boucles infinies dans des services stateless**.

Render est stateless. Les conteneurs peuvent redémarrer à tout moment. Une boucle de polling qui dépend d'un état persistant (lock fichier, état IMAP) est une recette pour le désastre.

### La solution Gmail Push

Gmail Apps Script est stateless. Il pousse les événements quand ils arrivent. Pas de boucle, pas de lock, pas d'état à maintenir.

**Le principe** : laisser le service stateless (Google) gérer la boucle, et recevoir les événements de manière stateless.

---

## La Golden Rule : Usine fermée, service postal actif

L'usine de polling IMAP est fermée, démantelée, et morte. Gmail Push est le seul service postal actif. Si vous voyez du code IMAP, c'est soit historique, soit à supprimer. Chaque décision (❌/✅, trade-offs, misconceptions) maintient la propreté du service postal.

Pour l'ingestion actuelle : voir `docs/v2/ingestion/gmail-push.md`.

---

*Ce document est conservé pour mémoire. Toute référence au polling IMAP doit être remplacée par Gmail Push Ingress.*
