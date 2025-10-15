# Configuration de l'authentification Gmail OAuth

Ce guide explique comment configurer l'authentification OAuth 2.0 pour envoyer des e-mails via l'API Gmail.

## Prérequis

1. Un compte Google (Gmail)
2. Accès à [Google Cloud Console](https://console.cloud.google.com/)
3. Accès à [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)

## Étape 1 : Configurer un projet dans Google Cloud Console

1. Allez sur [Google Cloud Console](https://console.cloud.google.com/)
2. Créez un nouveau projet ou sélectionnez-en un existant
3. Activez l'API Gmail :
   - Allez dans "APIs et services" > "Bibliothèque"
   - Recherchez "Gmail API"
   - Cliquez sur "Activer"

## Étape 2 : Configurer l'écran de consentement OAuth

1. Dans la console, allez dans "APIs et services" > "Écran de consentement OAuth"
2. Sélectionnez le type d'utilisateur (Externe ou Interne)
3. Remplissez les informations requises :
   - Nom de l'application
   - E-mail de support
   - E-mail du contact de la protection des données
4. Cliquez sur "Enregistrer et continuer"
5. Pour les champs de portée, vous pouvez ignorer pour l'instant
6. Ajoutez-vous comme utilisateur de test

## Étape 3 : Générer les identifiants OAuth 2.0

1. Allez dans "Identifiants" > "Créer des identifiants" > "ID client OAuth"
2. Sélectionnez "Application de bureau"
3. Donnez un nom à votre application
4. Notez l'**ID client** et le **secret client** générés

## Étape 4 : Obtenir un refresh token via OAuth Playground

1. Allez sur [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Cliquez sur l'icône d'engrenage (⚙️) en haut à droite
3. Cochez "Utiliser vos propres identifiants OAuth"
4. Entrez votre **ID client** et **secret client**
5. Cliquez sur "Fermer"
6. Dans la section "Sélectionner et autoriser les API", entrez :
   ```
   https://www.googleapis.com/auth/gmail.send
   ```
7. Cliquez sur "Autoriser les API"
8. Connectez-vous avec votre compte Google si demandé
9. Cliquez sur "Échanger l'autorisation contre des jetons"
10. Copiez le **refresh_token** généré (commence par `1//`)

## Configuration des variables d'environnement

Ajoutez ces variables dans votre fichier `.env` ou dans les paramètres de votre hébergement :

```
GMAIL_CLIENT_ID=votre_id_client
GMAIL_CLIENT_SECRET=votre_secret_client
GMAIL_REFRESH_TOKEN=le_refresh_token_obtenu
GMAIL_FROM_EMAIL=votre_email@gmail.com
AUTOREPONDEUR_TO=destinataire@example.com
```

## Dépannage

- **Erreur "invalid_grant"** : Le refresh token a expiré. Générez-en un nouveau.
- **Erreur d'autorisation** : Vérifiez que vous avez accordé les bonnes autorisations (scope: `gmail.send`)
- **E-mails non reçus** : Vérifiez le dossier spam et les journaux d'erreurs

## Sécurité

- Ne partagez jamais votre `client_secret` ou `refresh_token`
- Régénérez vos jetons régulièrement
- Utilisez des variables d'environnement pour stocker les identifiants

## Références

- [Documentation de l'API Gmail](https://developers.google.com/gmail/api/guides)
- [Guide OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
