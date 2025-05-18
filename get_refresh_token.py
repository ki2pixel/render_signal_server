from msal import PublicClientApplication # PublicClientApplication est adapté pour ce flux manuel
import json
import os

# Infos de votre inscription d'application (celle pour "Comptes personnels")
CLIENT_ID = "6bbc767d-53e8-4b82-bd49-480d4c157a9b" # Votre nouvel ID client
AUTHORITY = "https://login.microsoftonline.com/consumers" # Pour les comptes personnels
SCOPES = ["Files.ReadWrite", "offline_access", "User.Read"] # Permissions déléguées demandées
# L'URI de redirection que vous avez configurée dans Entra ID
REDIRECT_URI = "https://login.microsoftonline.com/common/oauth2/nativeclient" 

app = PublicClientApplication(CLIENT_ID, authority=AUTHORITY)

# 1. Obtenir l'URL d'autorisation
flow = app.initiate_auth_code_flow(scopes=SCOPES, redirect_uri=REDIRECT_URI)
auth_url = flow['auth_uri']
print(f"Ouvrez cette URL dans votre navigateur et connectez-vous:\n\n{auth_url}\n")
print("Après vous être connecté et avoir consenti, le navigateur sera redirigé vers une URL.")
print(f"Cette URL de redirection (qui commencera par '{REDIRECT_URI}') contiendra un paramètre 'code'.")

# 2. L'utilisateur copie le code d'autorisation depuis l'URL de redirection
auth_code = input("Collez le code d'autorisation complet (la valeur du paramètre 'code') ici: ")

# 3. Échanger le code d'autorisation contre des jetons
try:
    result = app.acquire_token_by_auth_code_flow(
        auth_code_flow=flow, # Le 'flow' initié précédemment
        auth_code=auth_code.strip(), # Le code collé par l'utilisateur
        scopes=SCOPES, # Redemander les scopes
        redirect_uri=REDIRECT_URI
    )
except ValueError as e:
    print(f"Erreur lors de l'acquisition du token (vérifiez le code et l'URI de redirection): {e}")
    exit()


if "access_token" in result and "refresh_token" in result:
    print("\n--- Succès ! ---")
    print(f"Access Token (courte durée):\n{result['access_token'][:50]}...\n")
    print(f"Refresh Token (longue durée - À CONSERVER PRÉCIEUSEMENT):\n{result['refresh_token']}\n")
    
    # Sauvegarder le refresh token dans un fichier (optionnel, mais pratique)
    refresh_token_file = "onedrive_refresh_token.txt"
    with open(refresh_token_file, "w") as f:
        f.write(result['refresh_token'])
    print(f"Le Refresh Token a été sauvegardé dans : {os.path.abspath(refresh_token_file)}")
    print("Vous devez maintenant mettre cette valeur de Refresh Token dans la variable d'environnement ONEDRIVE_REFRESH_TOKEN sur Render.com.")

elif "error_description" in result:
    print(f"\n--- Erreur lors de l'obtention des jetons ---")
    print(f"Erreur: {result.get('error')}")
    print(f"Description: {result.get('error_description')}")
    print(f"Détails: {result}")
else:
    print("\nRéponse inattendue lors de l'obtention des jetons:")
    print(json.dumps(result, indent=2))