Il est tout à fait possible et courant de piloter l'activation et la désactivation de vos scénarios Make (anciennement Integromat) en utilisant leur API. C'est très pratique pour intégrer la gestion de vos workflows dans des applications externes, des scripts ou des tableaux de bord.

Voici la méthode détaillée, étape par étape.

### Ce dont vous aurez besoin

1.  **L'ID de votre Scénario** : Chaque scénario sur Make a un identifiant numérique unique. Pour le trouver, ouvrez votre scénario dans l'éditeur. L'URL dans la barre d'adresse de votre navigateur ressemblera à ceci :
    `https://eu1.make.com/34567/scenarios/123456/edit`
    Dans cet exemple, `123456` est l'ID de votre scénario.

2.  **Votre Clé d'API (API Key)** : Vous devez générer une clé d'API dans votre compte Make.

      * Cliquez sur votre profil en bas à gauche.
      * Allez dans la section **API**.
      * Générez une nouvelle clé si vous n'en avez pas. Copiez-la et conservez-la en lieu sûr.

-----

### Les Endpoints de l'API à utiliser

L'API de Make est très simple pour cette tâche. Vous utiliserez une méthode `POST` sur des endpoints spécifiques.

**Attention à votre région \!**
Make a des URLs de base différentes pour les régions US et EU.

  * **EU (Europe) :** `https://eu1.make.com/api/v2/`
  * **US (États-Unis) :** `https://us1.make.com/api/v2/`

#### 1\. Pour **Activer** (Démarrer) un Scénario

Vous allez envoyer une requête pour "démarrer" le scénario, ce qui correspond à l'activer (le passer sur "ON").

  * **Méthode HTTP :** `POST`
  * **URL :** `https://[votre_region].make.com/api/v2/scenarios/{scenarioId}/start`

#### 2\. Pour **Désactiver** (Arrêter) un Scénario

De la même manière, pour le désactiver (le passer sur "OFF"), vous utilisez l'endpoint "stop".

  * **Méthode HTTP :** `POST`
  * **URL :** `https://[votre_region].make.com/api/v2/scenarios/{scenarioId}/stop`

-----

### L'Authentification

Toutes les requêtes vers l'API de Make doivent être authentifiées en passant votre clé d'API dans l'en-tête (header) `Authorization`.

  * **Header :** `Authorization`
  * **Valeur :** `Token VOTRE_CLÉ_API`

-----

### Exemples concrets avec cURL

Voici des exemples de commandes que vous pouvez utiliser directement dans un terminal. N'oubliez pas de remplacer les placeholders.

#### Exemple pour ACTIVER un scénario :

```bash
curl --location --request POST 'https://eu1.make.com/api/v2/scenarios/123456/start' \
--header 'Authorization: Token VOTRE_CLÉ_API'
```

*Remplacez `123456` par l'ID de votre scénario et `VOTRE_CLÉ_API` par votre clé.*

#### Exemple pour DÉSactiver un scénario :

```bash
curl --location --request POST 'https://eu1.make.com/api/v2/scenarios/123456/stop' \
--header 'Authorization: Token VOTRE_CLÉ_API'
```

*Remplacez `123456` par l'ID de votre scénario et `VOTRE_CLÉ_API` par votre clé.*

### Réponse de l'API

Si votre requête est réussie, l'API vous retournera un code de statut `200 OK` avec un objet JSON confirmant l'action, qui ressemble généralement à ceci :

```json
{
    "scenario": {
        "id": 123456,
        "name": "Nom de mon scénario",
        "isactive": true  // ou false si vous l'avez arrêté
    }
}
```

### En résumé