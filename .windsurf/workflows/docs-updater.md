---
description: Analyse la Memory Bank, inspecte le code source impacté, et met à jour TOUTE la documentation associée.
---

---
description: Docs Updater (Standard Tools: Cloc/Radon + Quality Context)
---

# Workflow: Docs Updater — Standardized & Metric-Driven

> Ce workflow harmonise la documentation en utilisant l'analyse statique standard (`cloc`, `radon`, `tree`) pour la précision technique et les modèles de référence pour la qualité éditoriale.

## 🚨 Protocoles Critiques
1.  **Outils autorisés** : L'usage de `run_command` est **strictement limité** aux commandes d'audit : `tree`, `cloc`, `radon`, `ls`.
2.  **Contexte** : Initialiser le contexte en appelant l'outil `fast_read_file` du serveur fast-filesystem pour lire UNIQUEMENT `activeContext.md`. Ne lire les autres fichiers de la Memory Bank que si une divergence majeure est détectée lors du diagnostic.
3.  **Source de Vérité** : Le Code (analysé par outils) > La Documentation existante > La Mémoire.
4.  **Interdiction formelle** : Ne pas utiliser les outils `filesystem` (read_text_file) pour accéder au dossier `memory-bank/`. Passez toujours par le serveur MCP fast-filesystem pour garantir le tracking des tokens dans le Dashboard Kimi.

## Étape 1 — Audit Structurel et Métrique
Lancer les commandes suivantes configurées pour ignorer les rapports de couverture (`htmlcov`) et les fichiers de déploiement/debug.

1.  **Cartographie (Filtre Bruit)** :
    - `run_command "tree -L 2 -I '__pycache__|venv|node_modules|.git|htmlcov|debug|deployment|memory-bank'"`
    - *But* : Visualiser l'architecture modulaire (`email_processing`, `services`, `routes`, `background`).
2.  **Volumétrie (Code Source)** :
    - `run_command "cloc . --exclude-dir=tests,docs,venv,node_modules,htmlcov,debug,deployment,memory-bank --exclude-ext=json,txt,log --md"`
    - *But* : Quantifier le code Python réel (Core vs Tests) sans être pollué par les logs ou les assets HTML.
3.  **Complexité Cyclomatique (Python Core)** :
    - `run_command "radon cc . -a -nc --exclude='tests/*,venv/*,htmlcov/*,docs/*,deployment/*,setup.py'"`
    - *But* : Repérer les points chauds.
    - **Cibles probables** : `email_processing/orchestrator.py` et `app_render.py` sont souvent des zones denses à surveiller (Score C/D).
4.  **Exploration Scripts Approfondie** :
    - `run_command "tree -L 4 scripts/ background/ routes/ services/ -I '__pycache__|venv|node_modules|.git|htmlcov|debug|deployment|memory-bank'"`
    - *But* : Explorer en profondeur les répertoires de scripts utilitaires et services (scripts/, background/, routes/, services/ avec modules critiques comme orchestrator.py, api_ingress.py).
5.  **Volumétrie Scripts Spécialisés** :
    - `run_command "cloc scripts/ background/ routes/ services/ --exclude-dir=tests --exclude-ext=json,txt,log --md"`
    - *But* : Quantifier le code dans les scripts spécialisés et services pour identifier les zones de documentation potentiellement manquées.
6.  **Complexité Scripts Utilitaires** :
    - `run_command "radon cc scripts/ background/ routes/ services/ -a -nc --exclude='tests/*'"`
    - *But* : Évaluer la complexité des scripts et services critiques pour prioriser la documentation des utilitaires et fonctions complexes (comme check_new_emails_and_trigger_webhook, ingest_gmail).

## Étape 2 — Diagnostic Triangulé
Comparer les sources pour détecter les incohérences :

| Source | Rôle | Outil |
| :--- | :--- | :--- |
| **Intention** | Le "Pourquoi" | `fast_read_file` (via fast-filesystem) |
| **Réalité** | Le "Quoi" & "Comment" | `radon` (complexité), `cloc` (volume), `search` ou `advanced-search` |
| **Existant** | L'état actuel | `search_files` (sur `docs/`), `read_text_file` |

**Action** : Identifier les divergences. Ex: "Le module `deduplication` contient une logique Redis complexe (Lock) non documentée dans `docs/processing`."

## Étape 3 — Sélection du Standard de Rédaction
Choisir le modèle approprié selon le dossier ciblé :

- **Processing Logic** (`email_processing/`, `background/`) :
  - **Diagramme de Séquence** : Indispensable pour l'orchestrateur (IMAP -> Extraction -> Webhook).
  - **États** : Décrire les statuts de traitement.
- **API & Routes** (`routes/`) :
  - Mapping URL -> Service.
  - Sécurité (Auth tokens, Rate limits).
- **Services & Utils** (`services/`, `utils/`) :
  - Interface publique des classes.
  - Gestion des exceptions (R2, Redis).
- **Configuration** (`config/`) :
  - Variables d'environnement requises (`settings.py`).
  - Flags d'exécution (`runtime_flags.py`).

## Étape 4 — Proposition de Mise à Jour
Générer un plan de modification avant d'appliquer :

```markdown
## 📝 Plan de Mise à Jour Documentation
### Audit Métrique
- **Cible** : `email_processing/link_extraction.py`
- **Métriques** : Complexité (B), Dépendance forte aux Regex.

### Modifications Proposées
#### 📄 docs/ingestion/gmail-push.md
- **Type** : [Logic/Algo]
- **Manque** : Les patterns Regex exacts ne sont pas listés.
- **Correction** :
  ```markdown
  [Ajout de la table de correspondance Regex -> Service]
```

## Étape 5 — Application et Finalisation
1.  **Exécution** : Après validation, utiliser `edit_file` ou `multi_edit`.
2.  **Mise à jour Memory Bank** :
    - Mettre à jour la Memory Bank en utilisant EXCLUSIVEMENT l'outil `fast_edit_block` du serveur fast-filesystem.

### Sous-protocole Rédaction — Application de documentation/SKILL.md

1. **Point d'entrée** : Après validation du plan (Étape 4), charger `.windsurf/skills/documentation/SKILL.md` via `read_text_file`.
2. **Modèle à appliquer** : Identifier le modèle (article deep-dive, README, note technique) préconisé par le skill et l'indiquer dans le plan.
3. **Checkpoints obligatoires** :
   - TL;DR présent (section 1 du skill)
   - Problem-first opening (section 2)
   - Bloc ❌/✅ le cas échéant (section 4)
   - Trade-offs table si comparaison (section 7)
   - Golden Rule / principe clé en conclusion (section 8)
   - Checklist « Avoiding AI-Generated Feel » appliquée
4. **Traçabilité** : Ajouter dans la proposition de mise à jour la mention « Guidé par documentation/SKILL.md — [sections appliquées] ».
5. **Validation finale** : Vérifier la ponctuation (remplacer " - " par ;/:/—) avant de clôturer la tâche.

## Technical Lockdown
Utilisez les outils fast-filesystem (fast_*) pour accéder aux fichiers memory-bank avec des chemins absolus.
- Windsurf is now in 'Token-Saver' mode. Minimize context usage by using tools instead of pre-loading.