# Contexte Actif

## Tâche en cours
- Ajustement des livraisons « Missions Recadrage » hors fenêtre horaire (report au prochain matin ouvré).

## Décisions récentes
- Résolution dédiée dans `email_processing/delivery_time_resolver.py`, branchée dans l'ingress Gmail Push et l'orchestrateur IMAP.
- Une cible hors de `[window_start, window_end)` est reportée à `09h00` le jour ouvré suivant ; le samedi est ouvré, le dimanche est exclu.
- Les livraisons en journée, les sujets `URGENCE`, les fenêtres absentes/invalides et les autres détecteurs restent inchangés.
- La date de réception utilisée est celle de l'email (ISO côté Apps Script, RFC 2822 côté IMAP), convertie en `Europe/Paris`.

## Questions Ouvertes
- Aucune.

## Prochaine Étape
- Surveiller les prochains lots nocturnes (`00hxx`) et vérifier la valeur `delivery_time` dans les logs webhook.
