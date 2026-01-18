# Audit Frontend – Dashboard Webhooks (Render Signal Server)

_Date : 2026-01-18_

## 1. Résumé exécutif
Frontend fonctionnel mais vieillissant. Le fichier `static/dashboard.js` (~1 400 lignes) reste monolithique, mélangeant appels API, logique métier et manipulation DOM, loin de l’architecture orientée services décrite dans la documentation. L’UX couvre les besoins de base (toasts, métriques, magic links) mais les feedbacks ne sont pas uniformes, la gestion des sessions est fragile (pas de redirection 401), et la responsivité mobile est limitée. Santé générale : **moyenne**, nécessite refontes progressives.

## 2. Problèmes critiques (sécurité & bugs fonctionnels)

| # | Gravité | Description | Référence |
|---|---------|-------------|-----------|
| 1 | 🔴 Sécurité | Aucun fetch ne gère explicitement les 401/403 ⇒ si la session expire, l’utilisateur reste bloqué sans redirection `/login`. | `static/dashboard.js` (`saveWebhookConfig`, `savePollingConfig`, `generateMagicLink`, etc.) |
| 2 | 🔴 Robustesse | `saveWebhookConfig` peut envoyer `***` (placeholder masqué) et écraser l’URL réelle du webhook. | `static/dashboard.js` L819-L858 |
| 3 | 🟠 Performance | `setInterval(loadWebhookLogs, 30000)` n’est jamais nettoyé ⇒ risques de multiples intervalles et de requêtes simultanées. | `static/dashboard.js` L1102-L1104 |
| 4 | 🟠 Accessibilité | Onglets sans rôles `tab`/`tabpanel`, focus non géré ⇒ navigation clavier déficiente. | `dashboard.html` L375-L382 |
| 5 | 🟠 Validation | Aucune validation `HHhMM` côté front pour les fenêtres horaires (contraire aux docs). | `static/dashboard.js` L612-L642 |

## 3. Analyse par axe

### 3.1 Architecture & qualité du code
- Monolithisme : un seul script combine utilitaires, appels réseau, logique métier et DOM. Pas de modules ES ni de services front alors que la documentation vante l’orientation services.
- Usage ES6 correct (async/await, const/let) mais global scope massif ; absence de classes ou de pattern module.
- Sélecteurs DOM dispersés. Aucun cache ni gestion centralisée, ce qui rigidifie l’UI.

### 3.2 Intégration API & gestion d’état
- `fetch` géré au cas par cas, pas de wrapper commun ⇒ duplication de try/catch et aucune interception session expirée.
- Fenêtres horaires envoyées brutes sans normalisation front ; erreurs 400 renvoyées par l’API mais peu lisibles côté UI.
- Export/import entremêle appels GET multiples sans mutualisation d’état.
- Polling des logs : intervalle perpétuel, pas de nettoyage, pas de pause sur `visibilitychange`.

### 3.3 UX & UI
- `showMessage` cohérent mais seuls certains boutons affichent un état “en cours”.
- Magic link : clipboard géré mais absence de fallback manuel.
- Pas de visibilité sur l’état R2 (aucun badge `r2_url` dans les logs).
- Grilles `minmax(500px, 1fr)` rendent l’interface difficile sur mobile (<500 px).

### 3.4 Sécurité Frontend (OWASP)
- Logs correctement échappés via `escapeHtml`, mais le risque principal vient de la persistance des placeholders masqués et de l’absence de redirection en cas de session expirée.
- Peu de `console.log` sensibles, mais certains `console.warn` exposent les payloads entiers en développement.

### 3.5 Accessibilité (a11y)
- Tabs sans rôles ARIA, pas de `aria-selected`, ni `aria-controls`.
- Toasts non annoncés (`aria-live` manquant).
- Formulaires longs sans jump links ni ordre de tabulation optimisé.

## 4. Plan de refactoring suggéré

### Priorités immédiates (Semaine 1)
1. **Wrapper `apiFetch`** : centraliser fetch + gestion 401/403 (redirection `/login`), toasts uniformes, journalisation limitée.
2. **Validation & placeholders** : bloquer l’envoi de `webhook_url` si champ vide/placeholder, vérifier `https://` côté front, afficher erreurs sur les champs horaires (utilitaire `normalizeTimeInput`).
3. **Timers & métriques** : stocker l’ID du polling des logs, nettoyer sur navigation/visibilitychange, éviter les doublons.
4. **Feedback boutons** : bouton “Enregistrer” → état disabled + libellé “Enregistrement…”, spinners CSS légers.

### Améliorations à moyen terme (Semaines 2-3)
1. **Modularisation** : découper `dashboard.js` en modules (`apiClient`, `webhookService`, `pollingService`, `logsView`, `uiState`). Option : bundler léger (esbuild/vite) ou import maps.
2. **Store d’état** : gérer `webhookConfig`, `pollingConfig`, `processingPrefs` dans un store observable pour éviter re-fetch multiples et faciliter la synchronisation UI.
3. **UX R2 & Magic Link** : afficher un badge `R2` sur les logs disposant d’un `r2_url`, proposer un bouton “Copier” de secours pour les magic links.
4. **Responsive** : ajuster CSS grid (`minmax(280px, 1fr)`), nav tabs scrollables, cartes en colonne unique <768 px.

### Améliorations futures (Semaine 4+)
1. **Accessibilité** : implémenter rôles ARIA pour les tabs, `aria-live="polite"` sur `status-msg`, focus management.
2. **Tests UI** : scénarios Playwright pour vérifier sauvegarde config, génération magic link, import/export.
3. **Framework léger (optionnel)** : envisager Preact/Lit pour structurer les cartes si la complexité continue d’augmenter.
4. **Instrumentation** : logs de performance front (durée fetch) et alignement avec les métriques backend.
