# Guide de Migration vers Gmail Push Ingress

**Date** : 2026-02-04  
**Statut** : ✅ **OPERATIONNEL** - Guide complet pour la migration depuis IMAP polling vers Gmail Push

---

## 🎯 Objectif

Ce guide aide les opérateurs à migrer de l'ancien système de polling IMAP vers le nouveau système d'ingestion Gmail Push, qui est plus fiable, plus rapide et plus simple à maintenir.

---

## 📋 Prérequis

- Accès administrateur à l'instance Render
- Accès au dashboard de l'application
- Connaissance de base de Google Apps Script
- `PROCESS_API_TOKEN` configuré dans les variables d'environnement Render

---

## 🔄 Étapes de Migration

### 1. Configuration du Token d'API Gmail Push

1. **Vérifier la variable d'environnement** :
   ```bash
   # Dans le dashboard Render
   PROCESS_API_TOKEN=votre_token_secret_ici
   ```

2. **Tester le token** :
   ```bash
   curl -X POST https://votre-instance.onrender.com/api/ingress/gmail \
     -H "Authorization: Bearer PROCESS_API_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"sender":"test@example.com","body":"test","subject":"test"}'
   ```

### 2. Configuration du Google Apps Script

1. **Créer un nouveau projet Apps Script** :
   - Allez sur [script.google.com](https://script.google.com)
   - Créez un nouveau projet

2. **Configurer le trigger Gmail** :
   ```javascript
   // Dans l'éditeur Apps Script
   function setupGmailTrigger() {
     // Crée un trigger qui s'exécute quand un nouvel email arrive
     ScriptApp.newTrigger('processGmailMessage')
       .forUser()
       .onFormSubmit()
       .create();
   }
   ```

3. **Implémenter la fonction de traitement** :
   ```javascript
   function processGmailMessage(e) {
     const message = e.gmail.getMessageId();
     const messageData = GmailApp.getMessageById(message);
     
     const payload = {
       subject: messageData.getSubject() || "",
       sender: messageData.getFrom(),
       body: messageData.getPlainBody(),
       date: messageData.getDate().toISOString()
     };
     
     const url = "https://votre-instance.onrender.com/api/ingress/gmail";
     const token = PropertiesService.getScriptProperties().getProperty("PROCESS_API_TOKEN");
     
     const options = {
       method: "post",
       contentType: "application/json",
       headers: {
         Authorization: "Bearer " + token
       },
       payload: JSON.stringify(payload),
       muteHttpExceptions: true
     };
     
     const response = UrlFetchApp.fetch(url, options);
     const result = JSON.parse(response.getContentText());
     
     if (result.success) {
       Logger.log("Email pushed: " + result.status);
     } else {
       Logger.log("Push failed: " + result.message);
     }
   }
   ```

4. **Stocker le token Apps Script** :
   ```javascript
   // Exécuter une fois pour stocker le token
   function storeToken() {
     PropertiesService.getScriptProperties()
       .setProperty("PROCESS_API_TOKEN", "votre_token_secret_ici");
   }
   ```

### 3. Désactivation des Tâches IMAP

1. **Supprimer les variables d'environnement IMAP** (optionnel, pour le nettoyage) :
   ```bash
   # Dans le dashboard Render, supprimer :
   # ENABLE_BACKGROUND_TASKS
   # EMAIL_ADDRESS
   # EMAIL_PASSWORD
   # IMAP_SERVER
   # EMAIL_POLLING_INTERVAL_SECONDS
   # POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
   # BG_POLLER_LOCK_FILE
   ```

2. **Vérifier que plus aucun thread de polling n'est actif** :
   - Consultez les logs Render
   - Cherchez des messages `background_email_poller` ou `polling_thread`
   - Il ne devrait y en avoir aucun après 5 minutes

### 4. Validation du Flux Complet

1. **Envoyer un email de test** vers l'adresse Gmail configurée

2. **Vérifier les logs** :
   ```bash
   # Dans les logs Render, cherchez :
   API INGRESS: Gmail push processed successfully
   ```

3. **Vérifier le dashboard** :
   - Allez sur `/dashboard`
   - Consultez la section "📜 Historique des Webhooks (7 derniers jours)"
   - L'email traité devrait apparaître avec le statut `processed`

### 5. Monitoring et Alertes

1. **Configurer l'alerte Gmail Push** :
   ```bash
   # Dans votre système de monitoring
   # Alerte si absence de "API INGRESS: Gmail push" pendant 15 minutes
   ```

2. **Surveiller les erreurs** :
   ```bash
   # Alertes sur les patterns :
   # INGRESS: 401 Unauthorized
   # INGRESS: 400 Invalid JSON payload
   # WEBHOOK_SENDER: Error sending webhook
   ```

---

## 🛠 Dépannage

### Problèmes Courants

| Symptôme | Cause | Solution |
|----------|-------|----------|
| 401 Unauthorized | `PROCESS_API_TOKEN` manquant ou incorrect | Vérifier la variable d'environnement Render |
| 400 Missing field | Apps Script n'envoie pas `sender` ou `body` | Corriger le payload Apps Script |
| Aucun log INGRESS | Apps Script non configuré | Vérifier le trigger Gmail et le token |
| Webhooks non envoyés | `webhook_sending_enabled` à false | Activer via dashboard |

### Logs Utiles

```bash
# Logs de succès
API INGRESS: Gmail push processed successfully
WEBHOOK_SENDER: Webhook sent successfully to https://example.com/webhook

# Logs d'erreur
INGRESS: 401 Unauthorized - Invalid or missing PROCESS_API_TOKEN
WEBHOOK_SENDER: Error sending webhook - Connection timeout
```

---

## 📊 Avantages de la Migration

### Avant (IMAP Polling)
- ❌ Polling périodique (latence)
- ❌ Quotas IMAP limités
- ❌ Complexité des tâches de fond
- ❌ Verrous distribués nécessaires
- ❌ Maintenance des timeouts

### Après (Gmail Push)
- ✅ Ingestion instantanée
- ✅ Pas de quotas Apps Script
- ✅ Architecture simple (endpoint REST)
- ✅ Pas de verrous nécessaires
- ✅ Maintenance réduite

---

## 🔄 Rollback (en cas de problème)

Si Gmail Push ne fonctionne pas, vous pouvez temporairement réactiver le polling :

1. **Restaurer les variables IMAP** :
   ```bash
   ENABLE_BACKGROUND_TASKS=true
   EMAIL_ADDRESS=votre_email@gmail.com
   EMAIL_PASSWORD=votre_mot_de_passe_app
   IMAP_SERVER=imap.gmail.com
   ```

2. **Redémarrer l'application** sur Render

3. **Contactez l'équipe de support** pour diagnostiquer le problème Gmail Push

---

## 📚 Références

- **Documentation Gmail Push** : [gmail_push_ingress.md](features/gmail_push_ingress.md)
- **API Reference** : [api.md](architecture/api.md)
- **Plan de retraite IMAP** : [retirement_imap_polling_plan.md](retirement_imap_polling_plan.md)
- **Support Google Apps Script** : [developers.google.com/apps-script](https://developers.google.com/apps-script)

---

## ✅ Checklist de Migration

- [ ] `PROCESS_API_TOKEN` configuré et testé
- [ ] Apps Script Gmail créé et fonctionnel
- [ ] Token Apps Script stocké
- [ ] Trigger Gmail configuré
- [ ] Variables IMAP supprimées (optionnel)
- [ ] Flux de test validé
- [ ] Monitoring configuré
- [ ] Équipe formée au nouveau système

---

*Pour toute question ou problème, contactez l'équipe d'exploitation.*
