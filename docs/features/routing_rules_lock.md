# Verrouillage Routage Dynamique

## 📅 Date de création
2026-01-29

## Contexte
Le moteur de routage dynamique permet une grande flexibilité dans la configuration des règles de traitement des emails. Pour prévenir les modifications accidentelles qui pourraient perturber le flux de production, un mécanisme de verrouillage a été implémenté, offrant une sécurité maximale par défaut.

## Sécurité par défaut

### Principe de fonctionnement
- **État par défaut** : Verrouillé (🔒)
- **Philosophie** : "Sécurité d'abord" - l'utilisateur doit consciemment déverrouiller pour modifier
- **Auto-verrouillage** : Verrouillage automatique après chaque sauvegarde réussie
- **Persistance** : État du verrou non persisté (réinitialisation au rechargement)

## Interface utilisateur

### Cadenas dans l'en-tête
- **Position** : En-tête du panneau "Routage Dynamique"
- **Icônes** : 🔒 (verrouillé) / 🔓 (déverrouillé)
- **Interaction** : Click simple pour basculer l'état
- **Tooltips** : Messages contextuels dynamiques

### États visuels

#### Verrouillé (🔒)
- **Icône** : 🔒
- **Tooltip** : "Déverrouiller pour modifier les règles"
- **Champs** : Désactivés (opacity 0.6, pointer-events none)
- **Actions** : Boutons "Ajouter", "Supprimer", "Déplacer" désactivés
- **Sauvegarde** : Bouton "Sauvegarder" désactivé

#### Déverrouillé (🔓)
- **Icône** : 🔓
- **Tooltip** : "Verrouiller pour sécuriser les règles"
- **Champs** : Activés (opacity 1.0, pointer-events auto)
- **Actions** : Tous les boutons d'édition activés
- **Sauvegarde** : Bouton "Sauvegarder" activé si modifications

## Implémentation technique

### Service JavaScript
```javascript
// static/services/RoutingRulesService.js
class RoutingRulesService {
  constructor() {
    this._isLocked = true;  // Verrouillé par défaut
  }
  
  toggleLock() {
    this._isLocked = !this._isLocked;
    this._updateUI();
  }
  
  _updateUI() {
    const lockIcon = document.getElementById('routingLockIcon');
    const allFields = document.querySelectorAll('.routing-rule input, .routing-rule select');
    const actionButtons = document.querySelectorAll('.routing-rule-actions button');
    
    if (this._isLocked) {
      lockIcon.textContent = '🔒';
      allFields.forEach(field => field.disabled = true);
      actionButtons.forEach(btn => btn.disabled = true);
    } else {
      lockIcon.textContent = '🔓';
      allFields.forEach(field => field.disabled = false);
      actionButtons.forEach(btn => btn.disabled = false);
    }
  }
}
```

### Gestion des états
- **Initialisation** : Verrouillage automatique au chargement du panneau
- **Basculement** : Toggle instantané avec mise à jour UI
- **Sauvegarde** : Verrouillage automatique après `saveRules()` réussie
- **Erreur** : Maintien du déverrouillage si sauvegarde échoue

### Feedback utilisateur
- **Visuel** : Changement immédiat de l'icône et des états des champs
- **Tooltips** : Messages contextuels pour guider l'utilisateur
- **Transitions** : Animations CSS fluides (0.2s) pour les changements d'état
- **Accessibilité** : ARIA labels pour les lecteurs d'écran

## Comportements détaillés

### Workflow de modification
1. **État initial** : Panneau verrouillé 🔒
2. **Déverrouillage** : Click sur le cadenas → 🔓
3. **Modification** : Édition des règles (champs activés)
4. **Sauvegarde** : Click sur "Sauvegarder" → API call
5. **Auto-verrouillage** : Si succès → 🔓 → 🔒 automatique
6. **Erreur** : Si échec → 🔓 reste déverrouillé pour correction

### Cas d'usage

#### Modification rapide
- Click sur 🔒 → 🔓
- Modification d'une condition
- Sauvegarde → Auto-verrouillage

#### Session de modification prolongée
- Click sur 🔒 → 🔓
- Modifications multiples (ajout/suppression/réorganisation)
- Sauvegarde manuelle → Auto-verrouillage
- Si besoin de continuer : Click sur 🔒 → 🔓

#### Consultation seule
- Panneau reste verrouillé 🔒
- Navigation dans les règles (lecture seule)
- Aucun risque de modification accidentelle

## Sécurité et prévention des erreurs

### Protection contre les modifications accidentelles
- **Double-action** : Déverrouiller + modifier = action consciente
- **Auto-verrouillage** : Pas d'oubli de reverrouillage
- **État non persisté** : Rechargement = retour à l'état sécurisé

### Validation des actions
- **Sauvegarde** : Validation backend avant acceptation
- **Rollback** : En cas d'erreur, l'état précédent est restauré
- **Logs** : Toutes les actions de verrouillage/déverrouillage sont loggées

### Audit trail
```javascript
// Logs des actions de verrouillage
console.log('ROUTING_LOCK: Unlocked by user');
console.log('ROUTING_LOCK: Auto-locked after save');
console.log('ROUTING_LOCK: Manual lock by user');
```

## Accessibilité

### Support lecteurs d'écran
- **ARIA labels** : "Verrouiller les règles de routage" / "Déverrouiller les règles de routage"
- **Rôles** : `role="button"` sur le cadenas
- **États** : `aria-pressed="true/false"` pour l'état du verrou

### Navigation clavier
- **Tab** : Navigation jusqu'au cadenas
- **Enter/Space** : Basculement du verrou
- **Focus** : Indicateur de focus visible sur le cadenas

### Contraste et visibilité
- **Icônes** : Taille suffisante (24px) et contraste élevé
- **États** : Opacité différente pour les champs désactivés
- **Transitions** : Animations respectant `prefers-reduced-motion`

## Personnalisation et configuration

### Options de comportement
```javascript
// Configuration possible (futur)
const lockConfig = {
  defaultLocked: true,        // État par défaut
  autoLockOnSave: true,       // Auto-verrouillage après sauvegarde
  autoLockDelay: 500,         // Délai avant auto-verrouillage (ms)
  requireConfirmation: false,  // Confirmation pour déverrouiller
  lockTimeout: 300000         // Auto-verrouillage après inactivité (5min)
};
```

### Thèmes visuels
- **Cork (défaut)** : Icônes emoji, transitions fluides
- **High-contrast** : Icônes SVG, contraste élevé
- **Minimal** : Texte "Verrouillé/Déverrouillé" uniquement

## Intégration avec l'écosystème

### Compatibilité
- **API** : Aucune modification nécessaire
- **Backend** : Le verrouillage est purement frontend
- **Tests** : Tests existants toujours valides

### Dépendances
- **JavaScript ES6** : Classes et modules
- **CSS Transitions** : Pour les animations fluides
- **LocalStorage** : Optionnel pour la persistance de préférences

## Évolution future

### Améliorations prévues
- **Permissions** : Verrouillage basé sur les rôles utilisateur
- **Collaboration** : Indicateur "En cours de modification par X"
- **Historique** : Log des modifications avec auteur et timestamp
- **Templates** : Verrouillage des templates partagés

### Fonctionnalités avancées
- **Verrouillage sélectif** : Verrouiller certaines règles seulement
- **Workflow** : Validation multi-étapes avant déverrouillage
- **Audit** : Export des actions de verrouillage pour audit

---

## Voir aussi
- [Moteur de Routage Dynamique](routing_rules_engine.md)
- [Documentation Frontend Dashboard](frontend_dashboard_features.md)
- [Architecture Modulaire ES6](../architecture/overview.md#architecture-frontend-modulaire-es6-2026-01-19)
