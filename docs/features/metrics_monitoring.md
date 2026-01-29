# Métriques & Monitoring Local

## 📅 Date de création
2026-01-29

## Contexte
Pour améliorer la visibilité de l'état du système, un système de métriques locales a été implémenté dans le dashboard, permettant aux utilisateurs de surveiller l'activité des webhooks et du polling en temps réel.

## Fonctionnalités

### Toggle d'activation
- **Nom** : "Activer le calcul de métriques locales"
- **État par défaut** : Activé (`checked`)
- **Persistance** : État sauvegardé dans `localStorage`
- **Impact** : Calcul automatique au premier chargement si activé

### Métriques calculées

#### Webhooks (24 heures)
- **Total envoyés** : Nombre de webhooks envoyés avec succès
- **Total échoués** : Nombre de webhooks en erreur
- **Taux de succès** : Pourcentage de réussite (arrondi à 1 décimale)
- **Dernier envoi** : Timestamp du dernier webhook réussi

#### Polling IMAP
- **Dernière vérification** : Timestamp du dernier cycle de polling
- **Emails traités** : Nombre d'emails traités lors du dernier cycle
- **Statut du poller** : Actif/Inactif selon la configuration

#### Performance
- **Latence moyenne** : Temps moyen de traitement des emails
- **Pic d'activité** : Période avec le plus grand nombre d'événements

## Architecture technique

### Fonctions JavaScript

#### Calcul et rendu
```javascript
// Calcule toutes les métriques et met à jour l'UI
computeAndRenderMetrics()

// Efface toutes les métriques de l'interface
clearMetrics()

// Met à jour une métrique spécifique
setMetric(metricId, value, trend)

// Crée un mini-graphique Canvas pour une métrique
renderMiniChart(canvasId, data, color)
```

#### Gestion du cycle de vie
- **Initialisation** : `loadLocalPreferences()` charge l'état du toggle
- **Sauvegarde** : `saveLocalPreferences()` persiste l'état dans localStorage
- **Auto-déclenchement** : Calcul automatique après chargement des données si toggle activé

### Sources de données

#### Logs des webhooks
- **Endpoint** : `/api/webhook_logs`
- **Période** : 7 derniers jours (filtré côté client pour 24h)
- **Champs** : timestamp, status, webhook_url, error_message

#### Statut du polling
- **Endpoint** : `/api/get_polling_config`
- **Champs** : enable_polling, last_execution, next_execution

#### Logs système
- **Endpoint** : `/api/logs`
- **Filtrage** : Messages préfixés `POLLER:`, `WEBHOOK:`

### Mini-graphiques Canvas

#### Configuration
- **Dimensions** : 120x40 pixels
- **Type** : Line chart avec remplissage semi-transparent
- **Animation** : Progressive (100ms) lors du premier rendu
- **Thème** : Cohérent avec le thème cork du dashboard

#### Données visualisées
- **Activité webhook** : Courbe d'envois par heure
- **Tendance polling** : Courbe de cycles par heure
- **Performance** : Courbe de latence moyenne

## Interface utilisateur

### Section "📊 Monitoring & Métriques (24h)"

#### Toggle principal
- **Label** : "Activer le calcul de métriques locales"
- **Comportement** : 
  - Coché : Calcul automatique, affichage des métriques
  - Décoché : Masquage des métriques, arrêt des calculs

#### Cartes de métriques
- **Layout** : Grille responsive 2x2 sur desktop, 1x2 sur mobile
- **Style** : Cartes avec icônes, valeurs, et tendances
- **Actualisation** : Manuel via bouton "🔄 Actualiser"

#### Graphiques
- **Position** : Sous les cartes de métriques
- **Responsive** : Adaptation mobile (largeur 100%)
- **Accessibilité** : Texte alternatif pour lecteurs d'écran

## Performance et optimisation

### Calcul côté client
- **Avantages** : Réduction de la charge serveur, temps réel
- **Inconvénients** : Limité aux données disponibles dans le dashboard

### Optimisations
- **Débouncing** : Pas de recalcul excessif lors des changements
- **Mise en cache** : Données de logs mises en cache dans le navigateur
- **Lazy loading** : Graphiques générés uniquement si la section est visible

### Limites
- **Période** : Maximum 24 heures (données locales)
- **Historique** : Pas de persistance entre les sessions
- **Précision** : Arrondi des pourcentages et timestamps

## Sécurité et confidentialité

### Données traitées
- **Logs** : Uniquement les métadonnées (timestamps, statuts)
- **Aucun contenu** : Pas de sujet d'email ou de payload webhook
- **Local uniquement** : Aucun envoi de données vers des services externes

### Masquage des informations sensibles
- **URLs** : Masquage automatique des URLs complètes dans les graphiques
- **Timestamps** : Format relatif ("il y a 2 heures") pour éviter l'empreinte temporelle exacte

## Évolution future

### Fonctionnalités prévues
- **Export** : Export CSV/PDF des métriques sur période personnalisée
- **Alertes** : Configuration d'alertes basées sur les métriques
- **Comparaison** : Comparaison période N vs période N-1
- **Prédictions** : Tendance et prédictions basées sur l'historique

### Améliorations techniques
- **WebSocket** : Mise à jour temps réel sans rechargement
- **Stockage** : Persistance IndexedDB pour l'historique local
- **Personnalisation** : Choix des métriques à afficher

## Intégration avec l'écosystème

### Compatibilité
- **Backend** : Aucune modification nécessaire
- **API** : Utilise les endpoints existants
- **Tests** : Tests unitaires pour les fonctions de calcul

### Dépendances
- **Canvas API** : Navigateur moderne requis
- **LocalStorage** : Doit être disponible (toujours le cas dans les navigateurs modernes)
- **Fetch API** : Pour la récupération des données

---

## Voir aussi
- [Documentation Frontend Dashboard](frontend_dashboard_features.md)
- [Architecture Modulaire ES6](../architecture/overview.md#architecture-frontend-modulaire-es6-2026-01-19)
- [Journalisation et Logs](../configuration/storage.md#journalisation)
