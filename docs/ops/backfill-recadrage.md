# Backfill recadrage 30 jours

**TL;DR** : `scripts/backfill_recadrage_emails.py` reconstruit l'archive publique servie par `email_proxy.php` à partir du mbox Gmail, sans jamais rejouer un email vers `index.php`. Il produit des JSON, un index fusionné et des archives prêtes à extraire dans `data/`.

---

## Le problème : une archive publique qui commence au déploiement

Le proxy email expose les missions de recadrage reçues depuis sa mise en service. Tout ce qui est arrivé avant n'existe que dans la boîte Gmail. Quand un client ouvre l'archive, il ne voit pas les lots de la période précédente, même si les fichiers sont toujours disponibles sur R2.

Rejouer les emails pour reconstruire l'historique serait pire que le problème : chaque rejeu vers `index.php` déclenche une réponse client. Il faut donc un outil qui lit le passé et écrit uniquement les fichiers de données.

---

## Ce que fait le script

Le script lit un export mbox, extrait les missions correspondant au pattern « Média Solution – Missions Recadrage », puis :

1. Extrait le lot, la date de réception, le créneau de livraison et les liens de dépôt.
2. Résout les créneaux hors fenêtre avec `email_processing.delivery_time_resolver`.
3. Enrichit les liens avec les paires `source_url` / `r2_url` de `webhook_links.json`.
4. Déduplique d'abord par identifiant, puis par paire `(lot, mois calendaire)`. Deux lots 268 d'octobre et de novembre restent deux missions distinctes.
5. Fusionne les entrées rétroactives avec l'index live, triées par `received_at` décroissant.
6. Écrit des fichiers détail, l'index, un payload PHP et les archives de déploiement.

Le script ne contacte jamais `index.php`. Aucun email de confirmation n'est envoyé au client.

---

## Utilisation

```bash
python3 scripts/backfill_recadrage_emails.py \
    --mbox debug/mails/a_exporter.mbox \
    --output-dir deployment/dist
```

Options utiles :

| Option | Effet |
| --- | --- |
| `--days 30` | Fenêtre par défaut : de `now` moins 30 jours à minuit jusqu'à la plus ancienne entrée live |
| `--since`, `--until` | Bornes explicites (ISO 8601 ou `YYYY-MM-DD`, `until` exclusive) |
| `--now` | Horodatage de référence pour la fenêtre et `stored_at` |
| `--live-index-url`, `--live-index-file` | Source de l'index live (URL ou fichier local) |
| `--links-url`, `--links-file` | Source des paires de liens R2 |
| `--webhook-config` | Fichier de fenêtre horaire (défaut : `debug/webhook_config.json`) |
| `--max-entries 200` | Taille maximale de l'index fusionné |
| `--allow-empty-live` | Autorise une fusion sans entrées live |
| `--no-network` | Interdit tout appel réseau ; `--live-index-file` devient obligatoire, les liens R2 utilisent `webhook_links.json` local ou restent vides |
| `--verbose` | Active les logs de progression |

Le script échoue avec un code retour non nul quand le mbox est absent, quand la borne de début dépasse la borne de fin, ou quand l'index live est injoignable sans `--live-index-file` ni `--allow-empty-live`. Un proxy R2 injoignable ne bloque pas le run : le script retombe sur le fichier local, ou poursuit sans enrichissement.

---

## Sorties

```
deployment/dist/
├── data/emails/<id>.json            # Détail d'une mission
├── data/emails_recadrage_index.json # Index fusionné
├── backfill_recadrage_30d.tar.gz    # Archive prête pour data/
├── backfill_recadrage_30d.zip
└── backfill_payloads_30d.json       # Payload d'import PHP
```

Le résumé affiché en fin d'exécution indique la fenêtre, le nombre de missions mbox, la taille de l'index live, la taille de l'index fusionné, le nombre de missions enrichies R2 et la présence éventuelle du Lot 115.

---

## Garanties et limites

| Approche | Rejoue les emails | Envoie au client | Reconstruit l'historique | Réversible |
| --- | --- | --- | --- | --- |
| Rejeu vers `index.php` | Oui | Oui | Oui | Non |
| Backfill par fichiers | Non | Non | Oui | Oui (archives) |

- La déduplication est volontairement limitée à `(lot, mois calendaire)` ; un lot recyclé d'un mois sur l'autre reste distinct.
- Les jours fériés ne sont pas gérés par le résolveur de créneaux ; le samedi est ouvré, le dimanche est exclu.
- L'import côté serveur PHP reste une étape séparée, sous `flock(LOCK_EX)`, avec un mode `--dry-run`.
- Le script suppose que le mbox contient les en-têtes et les corps d'origine ; un export tronqué produit des missions incomplètes.

---

## Validation

`tests/test_backfill_recadrage.py` couvre 37 scénarios : extraction mbox, déduplication inter-mois, fusion d'index, enrichissement R2, assainissement des liens, génération des archives et erreurs de fenêtre.

```bash
pytest tests/test_backfill_recadrage.py -v
```

Pour un run hermétique, combiner `--no-network` avec `--live-index-file` et `--links-file`.

---

## La Golden Rule : lire le passé, ne jamais le rejouer

Le backfill reconstruit des données, pas des effets de bord. Tant que l'outil écrit des fichiers et jamais vers `index.php`, une erreur reste corrigeable par un nouveau run ; un rejeu, lui, est irréversible pour le client.
