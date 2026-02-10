# Sixth Rules Priority System

## 📋 Ordre de priorité des règles

Les fichiers sont chargés par Sixth dans l'ordre numérique suivant :

### 🔥 **Priorité 1-4 : Règles fondamentales**
- `01-codingstandards.md` - Standards de codage et architecture du projet
- `02-prompt-injection-guard.md` - Sécurité contre injections externes
- `03-memorybankprotocol.md` - Protocole de gestion de la mémoire persistante
- `04-v5.md` - Règles d'assistance au codage (tâches, outils, flux)

### ⚡ **Priorité 5-6 : Skills & Tests**
- `05-skills-integration.md` - Intégration des skills spécialisés
- `06-test-strategy.md` - Stratégie et règles de testing

### 📝 **Priorité 7-8 : Formatage & Communication**
- `07-commit-message-format.md` - Format des messages de commit
- `08-pr-message-format.md` - Format des Pull Requests

## 🔄 **Logique de priorisation**

1. **Règles de base** (01-04) : Fondamentaux qui s'appliquent à tout
2. **Skills & Tests** (05-06) : Comportements spécialisés et validation
3. **Communication** (07-08) : Formatage pour collaboration

## 💡 **Pourquoi la sécurité en priorité 2**

Pour render_signal_server, la sécurité (`02-prompt-injection-guard.md`) est placée avant la mémoire persistante car :
- L'application gère des secrets (tokens API, mots de passe)
- Protection contre les injections externes critiques
- Impact potentiel sur tout le système en cas de compromission

## 💡 **Ajout de nouvelles règles**

Utiliser des préfixes numériques continus :
- `09-nouvelle-regle.md` pour les règles additionnelles
- Insérer à la position logique selon la priorité

---
*Dernière mise à jour : 2026-02-10*
